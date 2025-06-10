import logging

class State:
    def __init__(self, name):
        self.name = name
        # Each state can have its own logger if needed, or use the StateMachine's logger
        self.logger = logging.getLogger(f"State.{self.__class__.__name__}") 

    def on_event(self, event, state_machine): # Pass state_machine for context if needed
        self.logger.debug(f"Event '{event}' received in state '{self.name}'. No explicit transition defined. Staying in '{self.name}'.")
        return self # Default: no change

class StateMachine:
    def __init__(self, initial_state):
        self.state = initial_state
        self.subscribers = []
        self.logger = logging.getLogger('StateMachine')
        self.logger.info(f"StateMachine initialized. Initial state: {self.state.name}")


    def on_event(self, event):
        old_state_name = self.state.name
        self.logger.debug(f"Event: '{event}' received by StateMachine in state: '{old_state_name}'")
        
        # Pass self (the StateMachine instance) to the state's on_event method
        # This allows states to trigger further events or access other SM properties if necessary,
        # though direct state changes should still be returned.
        new_state_instance = self.state.on_event(event, self) 

        if new_state_instance is not self.state : # Check if a new state object was returned
            self.state = new_state_instance
            self.logger.info(f"State transition: '{old_state_name}' -> '{self.state.name}' on event '{event}'")
            self.notify_subscribers()
        else:
            self.logger.debug(f"No state change from '{old_state_name}' on event '{event}'.")


    def subscribe(self, callback):
        self.subscribers.append(callback)

    def notify_subscribers(self):
        for callback in self.subscribers:
            try:
                callback(self.state.name)
            except Exception as e:
                self.logger.error(f"Error in state change subscriber {callback}: {e}", exc_info=True)


class Disconnected(State):
    def __init__(self):
        super().__init__('DISCONNECTED')

    def on_event(self, event, state_machine): # Added state_machine param
        if event == 'connecting': # Initiator starts connection process
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'LogonInProgress'.")
            return LogonInProgress() # Assume TCP connect will follow, then Logon send
        elif event == 'tcp_connected': # Acceptor has a client, waiting for Logon
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'AwaitingLogon'.")
            return AwaitingLogon() 
        # 'connect' event was used before, if FixEngine changes to use 'connect', re-enable:
        # elif event == 'connect': # Generic connect event
        #     self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'LogonInProgress'.")
        #     return LogonInProgress()
        return super().on_event(event, state_machine)


class Connecting(State): # New state for initiator before TCP is up
    def __init__(self):
        super().__init__('CONNECTING')

    def on_event(self, event, state_machine):
        if event == 'connection_established': # After TCP connect succeeds
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'LogonInProgress'.")
            return LogonInProgress()
        elif event == 'connection_failed' or event == 'disconnect':
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        return super().on_event(event, state_machine)


class LogonInProgress(State): # Initiator waiting for Logon response
    def __init__(self):
        super().__init__('LOGON_IN_PROGRESS')

    def on_event(self, event, state_machine):
        if event == 'logon_successful': # Received valid Logon response
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Active'.")
            return Active()
        elif event == 'logon_failed' or event == 'disconnect':
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        return super().on_event(event, state_machine)


class AwaitingLogon(State): # New state for Acceptor after client TCP connect
    def __init__(self):
        super().__init__('AWAITING_LOGON')

    def on_event(self, event, state_machine):
        if event == 'logon_received_valid': # Received valid Logon from client
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Active'.")
            return Active()
        elif event == 'invalid_logon_received' or event == 'logon_timeout' or event == 'disconnect':
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        return super().on_event(event, state_machine)


class LogoutInProgress(State):
    def __init__(self):
        super().__init__('LOGOUT_IN_PROGRESS')

    def on_event(self, event, state_machine):
        if event == 'logout_confirmed' or event == 'disconnect': # e.g. received Logout response or peer disconnected
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        return super().on_event(event, state_machine)


class Active(State):
    def __init__(self):
        super().__init__('ACTIVE')

    def on_event(self, event, state_machine):
        if event == 'logout_initiated': # Application wants to log out
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'LogoutInProgress'.")
            return LogoutInProgress()
        elif event == 'disconnect': # Connection dropped or ungraceful disconnect
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        elif event == 'initiate_reconnect': # Initiator decides to reconnect (e.g. after disconnect)
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Reconnecting'.")
            return Reconnecting()
        return super().on_event(event, state_machine)


class Reconnecting(State): # Initiator attempting to reconnect
    def __init__(self):
        super().__init__('RECONNECTING')
        # This state implies a disconnect happened and now we are actively trying to reconnect.
        # It's similar to a sequence of Disconnected -> Connecting -> LogonInProgress

    def on_event(self, event, state_machine):
        # This state might primarily be managed by FixEngine's retry logic.
        # Events here would be from the outcome of a reconnect attempt.
        if event == 'connection_established': # Reconnect TCP attempt successful
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'LogonInProgress' (for resending Logon).")
            return LogonInProgress() # Need to send Logon again
        elif event == 'reconnect_failed_max_retries' or event == 'disconnect': # Give up or manual disconnect
            self.logger.debug(f"'{self.name}' handling '{event}': Transitioning to 'Disconnected'.")
            return Disconnected()
        return super().on_event(event, state_machine)
