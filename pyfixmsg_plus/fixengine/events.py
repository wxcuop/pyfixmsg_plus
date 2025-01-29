class EventNotifier:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, handler):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def notify(self, event_type, *args, **kwargs):
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                handler(*args, **kwargs)
