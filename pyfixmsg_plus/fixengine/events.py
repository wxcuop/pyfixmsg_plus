class EventNotifier:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, handler):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type, handler):
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(handler)

    def notify(self, event_type, event_data):
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                handler(event_data)
