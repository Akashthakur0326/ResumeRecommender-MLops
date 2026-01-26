"""from paddleocr import PaddleOCR
from .base_ingestor import BaseIngestor
import numpy as np
import cv2

# Initialize once (Global scope or Singleton pattern recommended for Prod)
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

class ImageIngestor(BaseIngestor):
    def extract(self, file_bytes) -> str:
        # Convert bytes to numpy array for OpenCV
        file_bytes = np.asarray(bytearray(file_bytes.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        
        result = ocr_engine.ocr(img, cls=True)
        
        extracted_text = []
        if result[0]:
            for line in result[0]:
                extracted_text.append(line[1][0]) # line[1][0] is the text
        
        return "\n".join(extracted_text)"""