"""Simulates a purely event-driven programming language.

This simulator is part of a computer science bachelor's thesis for the
University of Amsterdam, by Bas van den Heuvel. It follows all concepts
introduced in this thesis. The purpose is to be able to test and refine those
concepts.

The scheduling method is deterministicly sequential. No concurrent execution is
implemented.

Classes:
MachineControl -- manages and schedules state machines and events
Event -- event for communication between state machines
StateMachine -- superclass for all possible state machines
"""
from collections import deque as queue


class MachineControl:
    """Manage and schedule state machines and events.

    Every program created with this simulator should have an instance of this
    class. Starting a program goes through this instance, as well as
    instantiating state machines and sending events.

    Execution of its machine's states happens through cycles. The scheduling
    for this is sequential and very minimalistic: the first machine in its
    queue gets cycled after which it gets replaced at the end of the queue.

    It can be said that there is no event scheduling. Before each state cycle,
    all events in the event buss are distributed to their respective state
    machines.
    """

    def __init__(self, debug=False, step=False):
        """Initialize a machine control.

        It setups up a machine list, which in this implementation is a queue.
        Reaction maps are created as dictionaries, and the event buss is
        another queue.

        The `ctx` variable is not yet set. This happens when the simulator is
        started.

        Keyword arguments:
        debug -- prints state machine and event buss information if True
            (default True)
        step -- allows one to cycle stepwise (default False)
        """
        self.machines = queue()

        self.event_reactions = {}
        self.machine_reactions = {}

        self.event_buss = queue()

        self.ctx = None

        self.debug = debug
        self.react_event = None
        self.step = step

    def start_machine(self, machine_cls, ctx, *args, **kwargs):
        """Start a state machine.

        Initializes a machine, given arbitrary arguments, and adds it to the
        machine queue. After this, some event reactions are added for this
        machine, the `start' and the `halt' events. Finally, a `start' event is
        emitted to the newly created machine.

        Arguments:
        machine_cls -- a StateMachine subclass
        ctx -- the state machine that starts this new machine
        *args/**kwargs -- any arguments the state machine takes
        """
        machine = machine_cls(self, ctx, *args, **kwargs)

        self.machines.append(machine)

        self.add_machine_reaction('start', ctx, machine, machine.init_state)
        self.add_machine_reaction('halt', ctx, machine, machine.halt)

        self.emit(Event('start', ctx, destination=machine))

        return machine

    def add_event_reaction(self, typ, reactor, state):
        """Add a reaction to an event.

        Arguments:
        typ -- the event's type string
        reactor -- the StateMachine that should react
        state -- the state the machine should transition to, a method
        """
        if typ not in self.event_reactions:
            self.event_reactions[typ] = {}

        self.event_reactions[typ][reactor] = state

    def remove_event_reaction(self, typ, reactor):
        """Remove a reaction to an event.

        Arguments:
        typ -- the event's type string
        reactor -- the StateMachine that should ignore the event
        """
        try:
            del self.event_reactions[typ][reactor]
        except KeyError:
            pass

    def add_machine_reaction(self, typ, emitter, reactor, state):
        """Add a reaction to a state machine's event.

        Arguments:
        typ -- the event's type string
        emitter -- the event's emitting StateMachine
        reactor -- the StateMachine that should react
        state -- the state the machine should transition to, a method
        """
        index = (typ, emitter)

        if index not in self.machine_reactions:
            self.machine_reactions[index] = {}

        self.machine_reactions[index][reactor] = state

    def remove_machine_reaction(self, typ, emitter, reactor):
        """Remove a reaction to a state machine's event.

        Arguments:
        typ -- the event's type string
        emitter -- the event's emitting StateMachine
        reactor -- the StateMachine that should ignore the event
        """
        index = (typ, emitter)

        try:
            del self.machine_reactions[index][reactor]
        except KeyError:
            pass

    def emit(self, event):
        """Add an event to the event buss.

        Arguments:
        event -- the to be emitted Event
        """
        if self.debug:
            print('Emitting event:', event)

        self.event_buss.append(event)

    def run(self, machine_cls, *args, **kwargs):
        """Start a state machine and cycle until all machines have halted.

        A context is created for this first machine, by instantiating the
        StateMachine superclass without a context.

        Arguments:
        machine_cls -- a StateMachine subclass
        *args/**kwargs -- any arguments the state machine takes
        """
        self.ctx = StateMachine(self, None)
        self.start_machine(machine_cls, self.ctx, *args, **kwargs)

        while self.cycle():
            if self.step:
                input('Press enter to step...')

    def cycle(self):
        """Distribute events, cycle a machine and return whether any are left.

        When the machine queue is empty, False is returned. Otherwise, True is
        returned.
        """
        while self.distribute_events():
            pass

        try:
            machine = self.machines.popleft()
        except IndexError:
            return False

        self.machines.append(machine)

        c_state = machine.current_state

        if self.debug:
            print(type(machine).__name__)
            print('State:', c_state.__name__)
            print('Vars:', machine.var_str())

        machine.cycle()

        n_state = machine.current_state

        if self.debug:
            if c_state.__name__ == 'listen' and self.react_event is not None:
                print('Event:', self.react_event)
            if n_state is not None:
                print('=>', n_state.__name__)
            print()

        return True

    def distribute_events(self):
        """Distribute an event to machines and return whether any are left.

        If an event has a destination and that destination is still alive (i.e.
        not halted), the event is put into that machine's inbox.  Otherwise,
        the event is put into the inbox of all live machines, except the
        event's emitter.

        If an event has been distributed, True is returned. Otherwise, False is
        returned.
        """
        try:
            event = self.event_buss.popleft()
        except IndexError:
            return False

        if event.destination is not None:
            if event.destination in self.machines:
                event.destination.inbox.append(event)
            return True

        for machine in self.machines:
            if machine == event.emitter:
                continue
            machine.inbox.append(event)

        return True

    def filter_event(self, machine, event):
        """Returns a state if a machine should react to an event.

        If a reaction exists, the machine's reaction state is returned.
        Otherwise, None is returned.

        Arguments:
        machine -- the reacting state machine, a StateMachine
        event -- the event to be checked, an Event
        """
        if event.typ in self.event_reactions:
            try:
                return self.event_reactions[event.typ][machine]
            except KeyError:
                pass

        index = (event.typ, event.emitter)
        if index in self.machine_reactions:
            try:
                return self.machine_reactions[index][machine]
            except KeyError:
                pass

        return None

    def halt(self, machine):
        """Halt a machine."""
        self.machines.remove(machine)


class Event:
    """An event for interaction between state machines."""

    def __init__(self, typ, emitter, value=None, destination=None, ack=False):
        """Initialize the event.

        Arguments:
        typ -- the event's type string
        emitter -- the StateMachine emitting the event

        Keyword arguments:
        value -- value to transmit (default None)
        destination -- the StateMachine the event should end up with
            (default None)
        ack -- whether the receiving machine should emit an acknowledgement
            (default False)
        """
        self.typ = typ
        self.value = value
        self.emitter = emitter
        self.destination = destination
        self.ack = ack

        self.state = None

    def __repr__(self):
        return '<Event:typ=%s,emitter=%s,destination=%s,ack=%s>' % (
            self.typ, self.emitter, self.destination, self.ack)


class StateMachine:
    """Represent a state machine.

    To create purely event-driven programs, one can subclass this class. The
    `__init__` method should be extended with local variables and an initial
    state, but first call `super().__init__()` to prepare the machine.

    States can be implemented by adding methods to the class. The initial state
    can be indicated by setting `self.init_state` to the preferred state method
    in `__init__`. Loops are not impossible, but should not be used as they do
    not exist in the language proposed by this thesis.

    Do not override `listen` and `halt`, this will break the simulator.
    However, referring to both states is no problem (and usually necessary).

    The current event can be referred to through `self.event`. Do not mutate
    this variable.
    """

    def __init__(self, ctl, ctx):
        """Initialize the state machine.

        Prepares the machine for execution and prepares event processing
        necessities.

        Arguments:
        ctl -- a MachineControl instance
        ctx -- the machine's context, a StateMachine
        """
        self.ctl = ctl
        self.ctx = ctx

        self.current_state = self.listen

        self.inbox = queue()
        self.event = None

        self.init_state = self.halt

        self.info = []

    def var_str(self):
        """Create a string of formatted variables.

        `self.info` should contain a list of tuples with a format string and
        the name of a variable. This method aggregates them into a
        comma-separated string containing these formatted values.
        """
        values = [inf[0] % (getattr(self, inf[1])) for inf in self.info]
        return ', '.join(values)

    def cycle(self):
        """Run the current state and determine the next.

        If no next state is obtained, the new state will be 'listen`.
        """
        new_state = self.current_state()

        if self.current_state.__name__ == 'halt':
            new_state = self.current_state
        elif new_state is None:
            new_state = self.listen

        self.current_state = new_state

    def emit(self, typ, value=None):
        """Emit an event.

        Arguments:
        typ -- the event's type string

        Keyword arguments:
        value -- value to transmit with the event (default None)
        """
        self.emit_to(None, typ, value=value)

    def emit_to(self, destination, typ, value=None, ack_state=None):
        """Emit an event to a machine.

        Arguments:
        destination -- the StateMachine to send the event to
        typ -- the event's type string

        Keyword arguments:
        value -- value to transmit with the event (default None)
        ack_state -- a state for acknowledgement, a method

        If `ack_state` is given, the receiving machine will send an
        acknowledgement event. When the emitting machine recieves this event,
        it will transition to the given state.
        """
        self.ctl.emit(Event(typ, self, value=value, destination=destination,
                            ack=ack_state is not None))

        if ack_state is not None:
            self.when_machine_emits(typ + '_ack', destination, ack_state)

    def start_machine(self, machine_cls, *args, **kwargs):
        """Instantiate and start a machine.

        Arguments:
        machine_cls -- a StateMachine subclass
        *args/**kwargs -- any arguments the state machine takes
        """
        return self.ctl.start_machine(machine_cls, self, *args, **kwargs)

    def when_machine_emits(self, typ, machine, state):
        """Add a machine event reaction.

        Arguments:
        typ -- the event's type string
        machine -- the emitting StateMachine
        state -- the state to transition to, a method
        """
        self.ctl.add_machine_reaction(typ, machine, self, state)

    def when(self, typ, state):
        """Add an event reaction.

        Arguments:
        typ -- the event's type string
        state -- the state to transition to, a method
        """
        self.ctl.add_event_reaction(typ, self, state)

    def ignore_when_machine_emits(self, typ, machine):
        """Remove a machine event reaction.

        Besides ignoring further such events, all events from the given machine
        and of the given type in the machine's inbox are removed.

        Arguments:
        typ -- the event's type string
        machine -- the event's emitting StateMachine
        """
        self.ctl.remove_machine_reaction(typ, machine, self)

        inbox_prime = queue()
        while True:
            try:
                event = self.inbox.popleft()
            except IndexError:
                break

            if event.typ != typ or event.emitter != machine:
                inbox_prime.append(event)

        self.inbox = inbox_prime

    def ignore_when(self, typ):
        """Remove an event reaction.

        Besides ignoring further such events, all events from the given machine
        and of the given type in the machine's inbox are removed.

        Arguments:
        type -- the event's type string
        """
        self.ctl.remove_event_reaction(typ, self)

        inbox_prime = queue()
        while True:
            try:
                event = self.inbox.popleft()
            except IndexError:
                break

            if event.typ != typ:
                inbox_prime.append(event)

        self.inbox = inbox_prime

    def filter_event(self, event):
        """Return a state if a reaction to the event exists.

        Arguments:
        event -- the Event
        """
        return self.ctl.filter_event(self, event)

    def listen(self):
        """Listen state for all machines.

        Do not extend or override this method.

        Checks the event inbox for any events and possible reactions. If an
        acknowledgement is required, this is sent.
        """
        try:
            self.event = self.inbox.popleft()
        except IndexError:
            self.ctl.react_event = None
            return

        reaction = self.filter_event(self.event)

        if reaction is None:
            self.ctl.react_event = None
            return

        self.ctl.react_event = self.event

        if self.event.ack:
            self.emit_to(self.event.emitter, self.event.typ + '_ack',
                         value=self.event.value)

        return reaction

    def halt(self):
        """Halt state for all machines.

        Do not extend or override this method.

        First emits `halt', which halts all child machines. Then MachineControl
        is told to halt the machine.
        """
        self.emit('halt')
        self.ctl.halt(self)
