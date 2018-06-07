import datetime
import serial
# Repo specific imports
import util


class Action:
    # Default campo for actions
    campo = None

    # Default columns for an action csv
    cols = ['name', 'time']
    name = '-'

    # Serial communication defaults for Arduino (see .ino file)
    port = '/dev/'
    baud = 9600
    serial_command_dict = {'pump_on': 'a',
                           'pump_off': 'b',
                           'vlight_on': 'c',
                           'vlight_off': 'd',
                           'flight_on': 'e',
                           'flight_off': 'f',
                           }

    def __init__(self, action_dict, schedule):
        assert self.campo, 'Set campo before creating any action objects'
        self.s = schedule
        # Call proper action function
        action_func = getattr(self, action_dict['name'], None)
        assert callable(action_func), 'Could not find action in action function dictionary'
        action_func(**action_dict)

    def water(self, **kwargs):
        start_time = kwargs.get('start_time', None)
        duration = kwargs.get('duration', None)
        assert all([start_time, duration]), 'Action function missing arguments'
        # Start and stop times are based on current date
        start_time = datetime.datetime.combine(datetime.date.today(), eval(start_time))
        stop_time = start_time + eval(duration)
        # Add pump on and pump off serial commands to scheduler
        self.s.enterabs(time=start_time,
                        priority=1,
                        action=self.serial_command,
                        argument='pump_on',
                        kwargs={'action': 'water'})
        self.s.enterabs(time=stop_time,
                        priority=1,
                        action=self.serial_command,
                        argument='pump_off',
                        kwargs={'action': 'water'})

    def light(self, **kwargs):
        start_time = kwargs.get('start_time', None)
        duration = kwargs.get('duration', None)
        type = kwargs.get('type', None)
        assert all([start_time, duration, type]), 'Action function missing arguments'
        # Start and stop times are based on current date
        start_time = datetime.datetime.combine(datetime.date.today(), eval(start_time))
        stop_time = start_time + eval(duration)
        if type == 'veg' or type == 'full':
            # Add pump on and pump off serial commands to scheduler
            self.s.enterabs(time=start_time,
                            priority=1,
                            action=self.serial_command,
                            argument='vlight_on',
                            kwargs={'action': 'light', 'type': type})
            self.s.enterabs(time=stop_time,
                            priority=1,
                            action=self.serial_command,
                            argument='vlight_off',
                            kwargs={'action': 'light', 'type': type})

        if type == 'flow' or type == 'full':
            # Add pump on and pump off serial commands to scheduler
            self.s.enterabs(time=start_time,
                            priority=1,
                            action=self.serial_command,
                            argument='flight_on',
                            kwargs={'action': 'light', 'type': type})
            self.s.enterabs(time=stop_time,
                            priority=1,
                            action=self.serial_command,
                            argument='flight_off',
                            kwargs={'action': 'light', 'type': type})

    def image(self, **kwargs):
        raise NotImplementedError

    def serial_command(self, command, **kwargs):
        com = self.serial_command_dict[command]
        assert com, f'Serial command {com} not found'
        with serial.Serial(self.port, self.baud) as ser:
            ser.write(com.encode())
        kwargs['serial_command'] = command
        self.log(kwargs)

    @util.timer
    def log(self, **kwargs):
        new_row_dict = kwargs
        new_row_dict['name'] = self.name
        # Make new row entry in each of the plant files
        for plant in self.campo.list_plants():
            util.save_row(plant, new_row_dict)


if __name__ == '__main__':
    print('Running tests for actions.py')
    from campo import Campo
    import sched
    import time

    Action.campo = Campo('test_campo.csv')

    s = sched.scheduler(timefunc=datetime.datetime.now, delayfunc=time.sleep)

    # Unpack schedule yaml
    for action_dict in util.load_schedule('test.yaml')['actions']:
        # Create action instance and add it to the scheduler
        a = Action(action_dict, schedule=s)

    print(s)