
```markdown
# FIX Session Logic Implementation

This directory contains the implementation of the session logic for the FIX protocol. Below is a detailed explanation of how the code handles various session-related messages.

## Logon (35=A)

The logon process is initiated by the `LogonHandler` class, which creates and sends a logon message. The `logon` method in `FixEngine` handles the logon sequence:
- Creates a logon message using `FixMessageFactory`.
- Sets the appropriate sender, target, and sequence number.
- Sends the logon message and starts the heartbeat.

```python
class LogonHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        ...

async def logon(self):
    logon_message = FixMessageFactory.create_message('A')
    logon_message[49] = self.sender
    logon_message[56] = self.target
    logon_message[34] = self.message_store.get_next_outgoing_sequence_number()
    await self.send_message(logon_message)
    await self.heartbeat.start()
```

## Heartbeat (35=0)

Heartbeats are managed by the `HeartbeatHandler` class. Heartbeats are sent at regular intervals to ensure the session is alive.

```python
class HeartbeatHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.heartbeat.last_received_time = asyncio.get_event_loop().time()
        if '112' in message:
            self.heartbeat.test_request_id = None
```

## Test Request (35=1)

The `TestRequestHandler` class handles incoming test requests. If a test request is received, the system responds with a heartbeat.

```python
class TestRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.handle_test_request(message)
```

## Resend Request (35=2)

The `ResendRequestHandler` class processes resend requests. If there are sequence number gaps, it sends the missing messages or gap fill messages.

```python
class ResendRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        start_seq_num = int(message.get('7'))
        end_seq_num = int(message.get('16'))
        if end_seq_num == 0:
            end_seq_num = self.message_store.get_next_outgoing_sequence_number() - 1
        
        for seq_num in range(start_seq_num, end_seq_num + 1):
            stored_message = self.message_store.get_message(self.version, self.sender, self.target, seq_num)
            if stored_message:
                await self.send_message(stored_message)
            else:
                await self.send_gap_fill_message(seq_num)
```

## Reject (35=3)

The `RejectHandler` class handles reject messages, logging them and updating the sequence number.

```python
class RejectHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.logger.warning(f"Message rejected: {message}")
```

## Sequence Reset (35=4)

The `SequenceResetHandler` class manages sequence reset messages. It can either reset the sequence numbers or fill gaps in the sequence.

```python
class SequenceResetHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        gap_fill_flag = message.get('123', 'N')
        new_seq_no = int(message.get('36'))

        if new_seq_no <= self.message_store.get_next_incoming_sequence_number():
            await self.send_reject_message(message.get('34'), 36, 99, "Sequence Reset attempted to decrease sequence number")
            return

        if gap_fill_flag == 'Y':
            self.message_store.set_incoming_sequence_number(new_seq_no)
        else:
            self.message_store.set_incoming_sequence_number(new_seq_no)
```

## Logout (35=5)

The `LogoutHandler` class handles logout messages, disconnecting the session and updating the state.

```python
class LogoutHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.state_machine.on_event('disconnect')
        await self.disconnect()
```

## Message Processing

The `MessageProcessor` class registers handlers for different message types and processes incoming messages by delegating them to the appropriate handler.

```python
class MessageProcessor:
    def register_handler(self, message_type, handler):
        self.handlers[message_type] = handler

    async def process_message(self, message):
        message_type = message.get(35)
        handler = self.handlers.get(message_type)
        if handler:
            await handler.handle(message)
```

