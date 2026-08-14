import datetime
import requests
import uuid

class BoxStateMachine:
    def __init__(self, entry_coords, exit_coords, camera_id, api_url, target_event_type):
        """
        entry_coords: tuple of two sv.Point (start, end)
        exit_coords: tuple of two sv.Point (start, end)
        """
        import supervision as sv # lazy load to avoid clutter if used elsewhere
        
        self.camera_id = camera_id
        self.api_url = api_url
        self.target_event_type = target_event_type
        
        self.line_entry = sv.LineZone(start=entry_coords[0], end=entry_coords[1])
        self.line_exit = sv.LineZone(start=exit_coords[0], end=exit_coords[1])
        
        # State Dictionary structure:
        # { tracker_id: {"state": "NEW", "event_sent": False} }
        self.states = {}
        self.completed_ids = set() # HARD LOCK to prevent duplicates
        
    def update(self, detections):
        """
        Receives Supervision detections.
        Triggers line states and advances the FSM.
        Returns a list of newly confirmed tracker IDs inside this tick.
        """
        # Store the boolean arrays tracking crosses for this specific frame
        entry_in, entry_out = self.line_entry.trigger(detections)
        exit_in, exit_out = self.line_exit.trigger(detections)
        
        confirmed_this_tick = []

        if detections.tracker_id is None:
            return confirmed_this_tick

        for i, tracker_id in enumerate(detections.tracker_id):
            # Skip if this ID has ALREADY been counted
            if tracker_id in self.completed_ids:
                continue

            if tracker_id not in self.states:
                self.states[tracker_id] = {"state": "NEW", "event_sent": False, "confidence": 0.0}
                
            # Update confidence (store the latest or max confidence optionally, here we store latest)
            if detections.confidence is not None:
                self.states[tracker_id]["confidence"] = detections.confidence[i]
                
            current_state = self.states[tracker_id]["state"]
            
            # Transition Logic:
            # Check if this specific box crossed the lines *in this frame*
            if entry_in[i] or entry_out[i]:
                if not hasattr(self, "entry_memory"): self.entry_memory = set()
                self.entry_memory.add(tracker_id)
                
            if exit_in[i] or exit_out[i]:
                if not hasattr(self, "exit_memory"): self.exit_memory = set()
                self.exit_memory.add(tracker_id)

            crossed_entry = tracker_id in getattr(self, "entry_memory", set())
            crossed_exit = tracker_id in getattr(self, "exit_memory", set())

            # NEW -> LINE_1_CROSSED (if crossed Entry)
            if crossed_entry:
                if current_state == "NEW" or current_state == "ABORTED":
                    self.states[tracker_id]["state"] = "LINE_1_CROSSED"
            
            # LINE_1_CROSSED -> CONFIRMED (if crossed Exit)
            if crossed_exit:
                if current_state == "LINE_1_CROSSED":
                    self.states[tracker_id]["state"] = "CONFIRMED"
                    self.completed_ids.add(tracker_id) # Lock ID permanently
                    confirmed_this_tick.append(tracker_id)
        
        return confirmed_this_tick
        
    def confirm_and_publish(self, confirmed_ids):
        """
        Takes a list of newly confirmed IDs and fires events to the backend.
        """
        if not confirmed_ids:
            return
            
        # Group them into a single event or multiple single-box events? 
        # The user's prompt suggested one event per CONFIRMED object or a grouped one.
        # "N = number of distinct confirmed box tracks... quantity: 3"
        # We will bundle them if there are multiple.
        
        # We can also do individual events. 
        # For this POC, let's just send one bundled event for all confirmed in this frame.
        
        # Filter out those already sent to prevent duplicate events 
        # (Though our state machine shouldn't trigger them to the confirmed list again)
        valid_ids = [tid for tid in confirmed_ids if not self.states[tid]["event_sent"]]
        
        if not valid_ids:
            return
            
        # Optional: Use average confidence
        avg_conf = sum([self.states[tid].get("confidence", 0.0) for tid in valid_ids]) / len(valid_ids)
        
        event_id = f"{self.camera_id}-{uuid.uuid4().hex[:8].upper()}"
        
        event = {
            "event_id": event_id,
            "camera_id": self.camera_id,
            "event_type": self.target_event_type,
            "quantity": len(valid_ids),
            "tracker_ids": [int(tid) for tid in valid_ids],
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "confidence": float(avg_conf)
        }
        
        print(f"\n[EVENT GENERATED] {self.target_event_type} | ID: {event_id} | QTY: {len(valid_ids)}")
        
        # Fire event
        try:
            res = requests.post(self.api_url, json=event, timeout=2.0)
            if res.status_code == 200:
                for tid in valid_ids:
                    self.states[tid]["event_sent"] = True
        except Exception as e:
            print(f"NETWORK ERROR: Failed to send to backend -> {e}")
            # Do not mark as event_sent - can act as poor man's retry (though we won't re-enter this function automatically without queueing).
            # True robust systems would put this in a queue. For now, leave it.
