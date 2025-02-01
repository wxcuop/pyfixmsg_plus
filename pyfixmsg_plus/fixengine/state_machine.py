# pyfixmsg_plus/fixengine/state_machine.py

class State:
    def __init__(self, name):
        self.name = name

    def on_event(self, event):
        pass

class StateMachine:
    def __init__(self, initial_state):
        self.state = initial_state

    def on_event(self, event):
        self.state = self.state.on_event(event)

class Disconnected(State):
    def __init__(self):
        super().__init__('Disconnected')

    def on_event(self, event):
        if event == 'connect':
            return Connecting()
        return self

class Connecting(State):
    def __init__(self):
        super().__init__('Connecting')

    def on_event(self, event):
        if event == 'logon':
            return Active()
        elif event == 'disconnect':
            return Disconnected()
        return self

class Active(State):
    def __init__(self):
        super().__init__('Active')

    def on_event(self, event):
        if event == 'disconnect':
            return Disconnected()
        elif event == 'reconnect':
            return Reconnecting()
        return self

class Reconnecting(State):
    def __init__(self):
        super().__init__('Reconnecting')

    def on_event(self, event):
        if event == 'logon':
            return Active()
        elif event == 'disconnect':
            return Disconnected()
        return self

class LogoutInProgress(State):
    def __init__(self):
        super().__init__('LogoutInProgress')

    def on_event(self, event):
        if event == 'disconnect':
            return Disconnected()
        return self
