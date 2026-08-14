import os
import cv2
from ultralytics import YOLO
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge.config import LATEST_STAGING_OUTPUT, AUDIT_THRESHOLD, KNOWN_CARTON_DIMENSIONS

class StaticStackAudit:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "best.pt")
        self.model_path = model_path
        self.model = None

    def _load_model(self):
        if self.model is None:
            self.model = YOLO(self.model_path)

    def estimate_count(self, image_path=LATEST_STAGING_OUTPUT):
        """
        Loads the latest staging image, runs YOLO detection, 
        and estimates the visible stack count.
        """
        if not os.path.exists(image_path):
            return {"error": "Latest staging frame not found"}

        self._load_model()
        frame = cv2.imread(image_path)
        if frame is None:
            return {"error": "Could not read latest staging frame"}

        # Run inference
        results = self.model(frame, conf=0.45, iou=0.45, verbose=False)[0]
        
        boxes = results.boxes.xyxy.cpu().numpy()
        confidences = results.boxes.conf.cpu().numpy()

        if len(boxes) == 0:
            return {
                "estimated_count": 0,
                "confidence": 1.0,
                "bboxes_found": 0
            }

        # Phase 9: Apply volume math
        # Multiply visible front-face counts by known carton depth dimension
        # to calculate an estimated total (e.g. stack depth multiplier).
        stack_depth_multiplier = KNOWN_CARTON_DIMENSIONS.get("depth", 1)
        estimated_count = len(boxes) * stack_depth_multiplier
        avg_confidence = float(confidences.mean())

        return {
            "estimated_count": estimated_count,
            "confidence": avg_confidence,
            "bboxes_found": len(boxes)
        }

    def reconcile(self, live_inventory_count, audit_estimate):
        """
        Compares the live count against the audit estimate and produces PASS or WARNING.
        """
        difference = abs(live_inventory_count - audit_estimate)
        status = "PASS" if difference <= AUDIT_THRESHOLD else "WARNING"

        return {
            "status": status,
            "live_count": live_inventory_count,
            "audit_count": audit_estimate,
            "difference": difference,
            "threshold": AUDIT_THRESHOLD
        }

if __name__ == "__main__":
    audit = StaticStackAudit()
    result = audit.estimate_count()
    print("Test Static Audit:", result)
