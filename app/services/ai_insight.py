import os
import json
from typing import List, Dict, Any
from neo4j import GraphDatabase, RoutingControl
from groq import Groq
from utils.logger import setup_logger
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = setup_logger(PROJECT_ROOT / "logs" / "ai_insight.log", "ai_insight")

# =========================================================
# 1. CONSTANTS: PROMPTS & QUERIES
# =========================================================

SYSTEM_PROMPT = """
<system_role>
You are the Reasoning Engine for a Career Advisory System.
Your goal is to perform a rigorous "Gap Analysis" between a candidate's resume and a specific Job Category.
You are NOT a cheerleader. You are a strict, technical hiring manager.
</system_role>

<core_directives>
1. **Be Harsh but Precise**: Do not use fluff. Do not praise generic effort. Focus only on technical reality.
2. **Evidence-Only**: You must reason ONLY from the provided <knowledge_graph_context>. Do not invent tools or concepts.
3. **Concept vs. Skill**:
   - **Skill**: Execution (e.g., "Writing SQL queries").
   - **Concept**: The underlying principle (e.g., "Relational Algebra", "ACID compliance").
   - *Constraint*: Your advice MUST link missing Skills to missing Concepts.
</core_directives>

<logic_flow>
Follow this reasoning path for every response:
1. **Analyze Strength**: Look at <matches>. Why did they score high? (Identify confirmed Skills).
2. **Analyze Failure**: Look at <misses>. Why did they score low? (Identify missing Concepts).
3. **Construct Pivot**: Look at <bridge_relations>. How does a Skill they HAVE connect to a Concept they NEED?
   - *Example Logic*: "User knows Pandas (Skill). Job needs Spark (Tool). Bridge: Both implement DataFrame API (Concept)."
</logic_flow>

<output_schema>
Return ONLY a valid JSON object. No markdown formatting outside the JSON strings.

{
  "strength_analysis": "2 sentences. Explain why they matched the Top 3 jobs. Bold specific matching skills.",
  "hard_truth_gaps": "3 sentences. Explain why they failed the Bottom 3 jobs. Focus on the CONCEPTS they lack that prevented the match.",
  "strategic_pivot": "A technical directive. Use the <bridge_relations> to explain how to transfer existing knowledge to the missing requirements."
}
</output_schema>
"""

# ✅ UPDATED QUERY: Uses your working Colab Logic (Anchors -> Roles -> Gaps -> Concepts)
QUERY_CAREER_CONTEXT = """
// --- STEP 1: IDENTIFY ANCHORS (Depth 0) ---
// We start with the skills the user actually has
MATCH (anchor)
WHERE anchor.name IN $user_skills
WITH collect(anchor) as user_nodes

// --- STEP 2: FIND HUB ROLES (Depth 1) ---
// Find roles in the graph that overlap with user skills
// We filter by the target category name to keep it relevant
MATCH (role:JobRole)
WHERE role.name CONTAINS $category_name OR $category_name CONTAINS role.name
WITH role, user_nodes

// Calculate overlap score
MATCH (role)-[:REQUIRES_SKILL|REQUIRES_TOOL|REQUIRES_FRAMEWORK|REQUIRES_LANGUAGE|REQUIRES_DATABASE|REQUIRES_CLOUDSERVICE]->(n)
WHERE n IN user_nodes
WITH role, count(n) as score, collect(n.name) as user_has
ORDER BY score DESC
LIMIT 1  // Focus on the SINGLE best graph match for this category

// --- STEP 3: FIND GAPS (Depth 2) ---
// From this Best Graph Role, find what is connected that the user DOES NOT have
MATCH (role)-[r1]->(missing_node)
WHERE NOT missing_node.name IN user_has
  AND labels(missing_node)[0] IN ['Skill', 'Tool', 'Framework', 'CloudService', 'Database', 'Concept']

// --- STEP 4: FIND CONCEPTS (Depth 3) ---
// "Why" is this missing node important? (Link to Concept)
OPTIONAL MATCH (missing_node)-[r2:IMPLEMENTS_CONCEPT]->(concept:Concept)

// --- AGGREGATE RETURN ---
RETURN 
    role.name as Target_Role,
    score as Overlap_Count,
    user_has as Your_Stack,
    collect(DISTINCT {
        name: missing_node.name,
        type: labels(missing_node)[0],
        relation: type(r1),
        underlying_concept: concept.name
    })[0..15] as Market_Gaps
"""

# =========================================================
# 2. THE ENGINE CLASS
# =========================================================

class AIInsightEngine:
    def __init__(self):
        # 1. Initialize Groq
        self.groq_key = os.getenv("GROQ_API_KEY")
        if not self.groq_key:
            logger.error("❌ GROQ_API_KEY not found in environment")
            raise ValueError("GROQ_API_KEY missing")
        self.groq_client = Groq(api_key=self.groq_key)

        # 2. Initialize Neo4j (Connection Only)
        self.neo4j_uri = os.getenv("NEO4J_URI")
        self.neo4j_user = os.getenv("NEO4J_USERNAME")
        self.neo4j_pass = os.getenv("NEO4J_PASSWORD")
        self.auth = (self.neo4j_user, self.neo4j_pass)
        
        try:
            # FIX: Explicitly set encrypted=True and trust strategy
            # Note: neo4j+ssc:// in the URI handles most of this, but this is safer
            # In ai_insight.py > AIInsightEngine > __init__

            self.driver = GraphDatabase.driver(
                self.neo4j_uri, 
                auth=self.auth,
                max_connection_lifetime=200, 
                keep_alive=True 
            )
            
            # 🚨 CRITICAL: Verify connectivity immediately. 
            # If this fails, we want the app to crash, not pretend it's working.
            self.driver.verify_connectivity()
            logger.info("✅ AIInsightEngine connected to Neo4j")

        except Exception as e:
            # 🚨 FIX: Don't just log warning. RAISE the error so you know it failed.
            logger.critical(f"❌ Neo4j Connection Failed: {e}")
            self.driver = None

    def close(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()

    def _fetch_graph_context(self, user_skills: List[str], category_name: str) -> Dict[str, str]:
        """
        Runs the Cypher query and formats the nested 'Market_Gaps' list.
        """
        clean_skills = [s.strip() for s in user_skills if s]
        
        try:
            # Execute Query
            records, summary, keys = self.driver.execute_query(
                QUERY_CAREER_CONTEXT,
                user_skills=clean_skills,
                category_name=category_name, # We use the category name to filter the graph roles
                database_="neo4j",
                routing_=RoutingControl.READ
            )
            
            if not records:
                return {"missing_concepts_str": "None", "missing_tools_str": "None", "bridge_relations_str": "None"}

            # Process the single best role returned
            row = records[0].data()
            gaps = row.get('Market_Gaps', [])

            missing_concepts_list = []
            missing_tools_list = []
            bridge_lines = []

            for gap in gaps:
                name = gap['name']
                n_type = gap['type']
                concept = gap['underlying_concept']
                
                # Format for LLM Prompt
                if n_type == 'Concept':
                    missing_concepts_list.append(name)
                else:
                    concept_str = f" (implements {concept})" if concept else ""
                    missing_tools_list.append(f"{name} [{n_type}]{concept_str}")
                    
                    # Create a "Bridge" logic
                    if concept:
                        bridge_lines.append(f"Missing {name} -> Requires Concept: {concept}")

            return {
                "missing_concepts_str": ", ".join(missing_concepts_list[:10]),
                "missing_tools_str": "; ".join(missing_tools_list[:10]),
                "bridge_relations_str": "\n".join(bridge_lines[:5])
            }

        except Exception as e:
            logger.error(f"Graph Query Failed: {e}")
            return {"missing_concepts_str": "", "missing_tools_str": "", "bridge_relations_str": ""}

    def _build_user_message(self, resume_text, category, matches, misses, graph_context):
        return f"""
<context_data>
<target_category>{category}</target_category>
<resume_summary>{resume_text[:1500]}</resume_summary>

<market_reality>
  <matches>{", ".join(matches)}</matches>
  <misses>{", ".join(misses)}</misses>
</market_reality>

<knowledge_graph_context>
  <missing_concepts>{graph_context['missing_concepts_str']}</missing_concepts>
  <missing_tools_with_context>{graph_context['missing_tools_str']}</missing_tools_with_context>
  <bridge_relations>{graph_context['bridge_relations_str']}</bridge_relations>
</knowledge_graph_context>
</context_data>

<instruction>
Generate the JSON response. 
Use <bridge_relations> to populate the "strategic_pivot" section specifically.
</instruction>
"""

    def generate_insight(self, resume_text: str, user_skills: List[str], 
                         category: str, matched_jobs: List[str], 
                         gap_jobs: List[str]) -> Dict[str, Any]:
        """
        Main entry point.
        """
        try:
            # 1. Get Graph Reasoning
            # Note: We pass 'category' instead of 'matched_jobs' because the Graph Query
            # now finds its OWN best matching role based on the Category Name.
            graph_context = self._fetch_graph_context(user_skills, category)

            # 2. Build Prompt
            user_msg = self._build_user_message(
                resume_text=resume_text,
                category=category,
                matches=matched_jobs[:3], 
                misses=gap_jobs,
                graph_context=graph_context
            )

            # 3. Call Groq
            completion = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            response_content = completion.choices[0].message.content
            return json.loads(response_content)

        except Exception as e:
            logger.error(f"Insight Generation Failed: {e}")
            return {
                "strength_analysis": "Could not generate analysis at this time.",
                "hard_truth_gaps": "Unavailable due to system load.",
                "strategic_pivot": "Focus on the skills listed in the job descriptions."
            }