from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# 🛑 CRITICAL: This must match the volume mount path inside your Airflow Docker container!
# If you mount your code to /opt/airflow/dags/repo, change this variable.
PROJECT_ROOT = "/opt/airflow/dags/job_scan"

# Default arguments for the DAG
default_args = {
    'owner': 'mlops_engineer',
    'depends_on_past': False, #Today’s run does NOT depend on yesterday
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),#Wait 5 min before retry
}

# Define the DAG
# The schedule matches your Git cron: 1st, 7th, 13th, 20th, 27th of the month
with DAG(
    'adaptive_ingestion_and_drift',
    default_args=default_args,
    description='Manages data drift and triggers DVC ingestion pipeline',
    schedule_interval='0 0 1,7,13,20,27 * *',
    start_date=datetime(2026, 2, 2),
    catchup=False,
    tags=['mlops', 'drift_management', 'dvc'],
) as dag:

    # Task 1: Fail-fast DB check prevents running heavy pipeline unnecessarily.
    check_db = BashOperator(
        task_id='check_db_connectivity',
        bash_command=f"cd {PROJECT_ROOT} && python src/scripts/check_db.py",
    )

    # Task 2: Run your custom Drift Management SQL script
    manage_drift = BashOperator(
        task_id='analyze_and_update_drift_policy',
        bash_command=f"cd {PROJECT_ROOT} && python src/scripts/manage_drift.py",
    )

    # Task 3: Partial DVC Pull (Models & NLTK data)
    dvc_pull_models = BashOperator(
        task_id='dvc_pull_models',
        bash_command=f"cd {PROJECT_ROOT} && dvc pull models/all-mpnet-base-v2 artifacts/nltk_data",
    )

    # Task 4: Execute the main DVC Pipeline
    # This runs ingest -> process -> label -> build_vector_store
    dvc_repro = BashOperator(
        task_id='dvc_repro_pipeline',
        bash_command=f"cd {PROJECT_ROOT} && dvc repro",
    )

    # Task 5: Push the newly generated data/vectors to S3
    dvc_push = BashOperator(
        task_id='dvc_push_to_s3',
        bash_command=f"cd {PROJECT_ROOT} && dvc push",
    )

    # ------------------------------------------------------------------
    # DEFINE THE WORKFLOW DEPENDENCIES (The actual graph)
    # ------------------------------------------------------------------
    check_db >> manage_drift >> dvc_pull_models >> dvc_repro >> dvc_push