class State:
    def __init__(self, name):
        self.name = name

    def on_event(self, event):
        pass

class StateMachine:
    def __init__(self, initial_state):
        self.state = initial_state
        self.subscribers = []
        self.logger = logging.getLogger('StateMachine')  # Adding logger for debugging

    def on_event(self, event):
        self.logger.debug(f"Handling event: {event} in state: {self.state.name}")
        self.state = self.state.on_event(event)
        self.logger.debug(f"State transitioned to: {self.state.name}")
        self.notify_subscribers()

    def subscribe(self, callback):
        self.subscribers.append(callback)

    def notify_subscribers(self):
        for callback in self.subscribers:
            callback(self.state.name)

class Disconnected(State):
    def __init__(self):
        super().__init__('DISCONNECTED')

    def on_event(self, event):
        if event == 'connect':
            return LogonInProgress()
        return self

class LogonInProgress(State):
    def __init__(self):
        super().__init__('LOGON_IN_PROGRESS')

    def on_event(self, event):
        if event == 'logon':
            return Active()
        elif event == 'disconnect':
            return Disconnected()
        return self

class LogoutInProgress(State):
    def __init__(self):
        super().__init__('LOGOUT_IN_PROGRESS')

    def on_event(self, event):
        if event == 'disconnect':
            return Disconnected()
        return self

class Active(State):
    def __init__(self):
        super().__init__('ACTIVE')

    def on_event(self, event):
        if event == 'disconnect':
            return Disconnected()
        elif event == 'reconnect':
            return Reconnecting()
        return self

class Reconnecting(State):
    def __init__(self):
        super().__init__('RECONNECTING')

    def on_event(self, event):
        if event == 'logon':
            return Active()
        elif event == 'disconnect':
            return Disconnected()
        return self
