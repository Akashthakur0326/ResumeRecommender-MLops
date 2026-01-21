#Image → OCR → text
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='en')
result = ocr.ocr("resume.jpg", cls=True)

text = " ".join([line[1][0] for line in result[0]])
