import datetime as dt
import unittest
from unittest.mock import patch

import icalendar
import pytz
from tzlocal import get_localzone
from freezegun import freeze_time

import remhind.events
from ..events import EventCollection, parse_rule, get_component_from_ics

VEVENT = """
BEGIN:VEVENT
UID:20190310
DTSTAMP:20190310T150000Z
DTSTART:20190310T150000Z
DTEND:20190310T160000Z
SUMMARY:Annual Employee Review
CLASS:PRIVATE
END:VEVENT
"""

VEVENT_ALARM = """
BEGIN:VEVENT
UID:20190310
DTSTAMP:20190310T150000Z
DTSTART:20190310T150000Z
DTEND:20190310T160000Z
SUMMARY:Breakfast Meeting
CLASS:PRIVATE
BEGIN:VALARM
TRIGGER:-PT30M
ACTION:DISPLAY
DESCRIPTION:Breakfast Meeting Reminder
END:VALARM
END:VEVENT
"""

VEVENT_DATE = """
BEGIN:VEVENT
UID:20190310
DTSTAMP:20190310T150000Z
DTSTART:20190310
SUMMARY:Birthday
CLASS:PRIVATE
END:VEVENT
"""

VEVENT_DATE_ALARM = """
BEGIN:VEVENT
UID:20190310
DTSTAMP:20190310T150000Z
DTSTART:20190310
SUMMARY:Breakfast Meeting
CLASS:PRIVATE
BEGIN:VALARM
TRIGGER:-PT30M
ACTION:DISPLAY
DESCRIPTION:Breakfast Meeting Reminder
END:VALARM
END:VEVENT
"""

VEVENT_RRULE = """
BEGIN:VEVENT
UID:20190310
DTSTAMP:20190310T150000Z
DTSTART:20190310T150000Z
SUMMARY:RRULE VEVENT
CLASS:PRIVATE
RRULE:FREQ=DAILY
BEGIN:VALARM
TRIGGER:-PT30M
ACTION:DISPLAY
DESCRIPTION:Breakfast Meeting Reminder
END:VALARM
END:VEVENT
"""

VTODO = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
DUE:20190310T170000Z
SUMMARY:Income Tax Preparation
PRIORITY:1
STATUS:NEEDS-ACTION
END:VTODO
"""

VTODO_DATE = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
DUE:20190310
SUMMARY:Income Tax Preparation
PRIORITY:1
STATUS:NEEDS-ACTION
END:VTODO
"""

VTODO_RRULE = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
DUE:20190310T170000Z
SUMMARY:Income Tax Preparation
PRIORITY:1
SEQUENCE:0
STATUS:NEEDS-ACTION
RRULE:FREQ=DAILY
END:VTODO
"""

VTODO_NO_DATE = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
SUMMARY:Income Tax Preparation
PRIORITY:1
STATUS:NEEDS-ACTION
END:VTODO
"""

VTODO_LONG_OVERDUE = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
DUE;TZID=Europe/Brussels:20100310T170000
SUMMARY:Income Tax Preparation
PRIORITY:1
STATUS:NEEDS-ACTION
END:VTODO
"""

VTODO_STARTING_SEQUENCE = """
BEGIN:VTODO
UID:20190310
DTSTAMP:20190310T150000Z
DUE:20100310T170000Z
SUMMARY:Income Tax Preparation
PRIORITY:1
SEQUENCE:2
STATUS:NEEDS-ACTION
RRULE:FREQ=DAILY
END:VTODO
"""

RRULE_EVENT = """
BEGIN:VEVENT
SUMMARY:Training
DTSTART;TZID=Europe/Brussels:20190207T100000
DTEND;TZID=Europe/Brussels:20190207T120000
DTSTAMP:20190131T153505
UID:BY8RPO6AXKEKM5EFBFN0W9
SEQUENCE:0
RRULE:FREQ=DAILY;COUNT=7;BYDAY=MO,TU,WE,TH,FR
RDATE;TZID=Europe/Brussels:20190401T100000,20190402T100000
EXDATE;TZID=Europe/Brussels:20190212T100000,20190213T100000
CLASS:PUBLIC
CREATED:20190131T153505
LAST-MODIFIED:20190131T153629
STATUS:CONFIRMED
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Training Reminder
TRIGGER:-PT1H
END:VALARM
END:VEVENT
"""

RRULE_TODO = """
BEGIN:VTODO
DTSTAMP:20190114T070828Z
UID:a8f5a030c6f94010a6654d79b8be5372@mirabelle
SEQUENCE:58
CREATED:20180316T230011Z
LAST-MODIFIED:20190114T070827Z
SUMMARY:Check something
STATUS:NEEDS-ACTION
RRULE:FREQ=MONTHLY;INTERVAL=4;BYDAY=3MO
DUE;VALUE=DATE:20190318
END:VTODO
"""


def setUpModule():
    remhind.events.LOCAL_TZ = pytz.timezone('Europe/Brussels')


def tearDownModule():
    remhind.events.LOCAL_TZ = get_localzone()


class TestEventFunction(unittest.TestCase):

    def test_parse_rrule(self):
        event = icalendar.Event.from_ical(RRULE_EVENT)
        ruleset = parse_rule(event)
        occurences = list(ruleset)

        self.assertEqual(len(occurences), 7)
        month_days = [
            (2, 7), (2, 8), (2, 11), (2, 14), (2, 15), (4, 1), (4, 2),
            ]
        for o, (month, day) in zip(occurences, month_days):
            with self.subTest(occurence=o):
                self.assertEqual((o.year, o.month, o.day), (2019, month, day))
                self.assertEqual((o.hour, o.minute), (10, 0))

    def test_get_component_from_ics(self):
        component = get_component_from_ics('20190310', VEVENT)
        self.assertEqual(component['uid'], '20190310')
        self.assertEqual(
            component['dtstart'].dt,
            dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC))

        component = get_component_from_ics('20190310', RRULE_TODO)
        self.assertIsNone(component)


class TestEventCollection(unittest.TestCase):

    def test_vevent(self):
        event = icalendar.Event.from_ical(VEVENT)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].event, '20190310')
        self.assertEqual(alarms[0].message, 'Annual Employee Review')
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC))

    def test_alarm_vevent(self):
        event = icalendar.Event.from_ical(VEVENT_ALARM)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 2)
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 14, 30, tzinfo=pytz.UTC))
        self.assertEqual(alarms[0].message, "Breakfast Meeting Reminder")
        self.assertEqual(
            alarms[1].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[1].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC))
        self.assertEqual(alarms[1].message, "Breakfast Meeting")

    def test_date_vevent(self):
        event = icalendar.Event.from_ical(VEVENT_DATE)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 1)
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))
        self.assertEqual(alarms[0].message, "Birthday")

    def test_date_alarm_vevent(self):
        event = icalendar.Event.from_ical(VEVENT_DATE_ALARM)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 2)
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 10, 30, tzinfo=pytz.UTC))
        self.assertEqual(alarms[0].message, "Breakfast Meeting Reminder")
        self.assertEqual(
            alarms[1].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[1].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))
        self.assertEqual(alarms[1].message, "Breakfast Meeting")

    @freeze_time('20190207', tz_offset=0)
    def test_rrule_event(self):
        event = icalendar.Event.from_ical(RRULE_EVENT)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 2, 7, 0, 0)
        end = dt.datetime(2019, 2, 10, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 4)
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 7, 9, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 7, 8, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[1].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 7, 9, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[1].date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 7, 9, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[2].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 8, 9, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[2].date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 8, 8, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[3].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 8, 9, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[3].date.astimezone(pytz.UTC),
            dt.datetime(2019, 2, 8, 9, 0, tzinfo=pytz.UTC))

    def test_vtodo(self):
        event = icalendar.Event.from_ical(VTODO)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 1)
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 17, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 17, 0, tzinfo=pytz.UTC))
        self.assertEqual(alarms[0].message, "Income Tax Preparation")

    def test_date_vtodo(self):
        event = icalendar.Event.from_ical(VTODO_DATE)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(2019, 3, 11, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 1)
        self.assertEqual(
            alarms[0].date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))
        self.assertEqual(
            alarms[0].due_date.astimezone(pytz.UTC),
            dt.datetime(2019, 3, 10, 11, 0, tzinfo=pytz.UTC))

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    def test_due_alarms(self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VEVENT_ALARM)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 12, 0, tzinfo=pytz.UTC)
        alarms = collection.get_due_alarms(start)
        self.assertEqual(len(alarms), 0)

        start = dt.datetime(2019, 3, 10, 14, 30, tzinfo=pytz.UTC)
        alarms = collection.get_due_alarms(start)
        self.assertEqual(len(alarms), 1)

        start = dt.datetime(2019, 3, 10, 15, 0, tzinfo=pytz.UTC)
        alarms = collection.get_due_alarms(start)
        self.assertEqual(len(alarms), 1)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    @freeze_time('20190310', tz_offset=0)
    def test_due_alarms_reccuring(self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VEVENT_RRULE)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        for day in range(15, 31):
            start = dt.datetime(2019, 3, day, 15, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), 1)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    @freeze_time('20190310', tz_offset=0)
    def test_due_todo_with_rrule(self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VTODO_RRULE)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        for idx, day in enumerate(range(10, 15)):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), idx + 1)

        # Simulate completion and the monitoring of the file
        completed_event = icalendar.Todo.from_ical(
            VTODO_RRULE.replace('NEEDS-ACTION', 'COMPLETED'))
        component_mock.return_value = completed_event
        collection.add(completed_event, None)

        for day in range(15, 31):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), 0)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    def test_due_todo_without_rrule(self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VTODO)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        for day in range(10, 15):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), 1)

        # Simulate completion and the monitoring of the file
        completed_event = icalendar.Todo.from_ical(
            VTODO.replace('NEEDS-ACTION', 'COMPLETED'))
        component_mock.return_value = completed_event
        collection.add(completed_event, None)

        for day in range(15, 31):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), 0)

    def test_todo_no_start(self):
        event = icalendar.Todo.from_ical(VTODO_NO_DATE)
        collection = EventCollection()
        collection.add(event, None)

        start = dt.datetime(2019, 3, 10, 0, 0)
        end = dt.datetime(9999, 12, 31, 0, 0)
        alarms = collection.db.get_alarms(start, end)

        self.assertEqual(len(alarms), 0)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    @freeze_time('20190310', tz_offset=0)
    def test_long_overdue_todo(self, path_mock, component_mock):
        event = icalendar.Todo.from_ical(VTODO_LONG_OVERDUE)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        noon = dt.datetime.now(tz=pytz.UTC).replace(hour=12)
        alarms = collection.get_due_alarms(noon)
        self.assertEqual(len(alarms), 0)

        tea_time = dt.datetime.now(pytz.UTC).replace(hour=16)
        alarms = collection.get_due_alarms(tea_time)
        self.assertEqual(len(alarms), 1)

        completed_event = icalendar.Todo.from_ical(
            VTODO_LONG_OVERDUE.replace('NEEDS-ACTION', 'COMPLETED'))
        component_mock.return_value = completed_event
        collection.add(completed_event, None)

        alarms = collection.get_due_alarms(tea_time)
        self.assertEqual(len(alarms), 0)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    @freeze_time('20190310', tz_offset=0)
    def test_due_todo_with_rrule_complete_some(
            self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VTODO_RRULE)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        for idx, day in enumerate(range(10, 15)):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), idx + 1)

        completed_event = icalendar.Todo.from_ical(
            VTODO_RRULE.replace('SEQUENCE:0', 'SEQUENCE:5'))
        component_mock.return_value = completed_event
        collection.add(completed_event, None)

        alarms = collection.get_due_alarms(start)
        self.assertEqual(len(alarms), 0)

        for idx, day in enumerate(range(15, 20)):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), idx + 1)

    @patch('remhind.events.get_component_from_ics')
    @patch('pathlib.Path.read_text')
    @freeze_time('20190310', tz_offset=0)
    def test_due_todo_with_sequence(self, path_mock, component_mock):
        event = icalendar.Event.from_ical(VTODO_STARTING_SEQUENCE)
        component_mock.return_value = event
        collection = EventCollection()
        collection.add(event, None)

        for idx, day in enumerate(range(10, 15)):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), idx + 1)

        completed_event = icalendar.Todo.from_ical(
            VTODO_STARTING_SEQUENCE.replace('SEQUENCE:2', 'SEQUENCE:4'))
        component_mock.return_value = completed_event
        collection.add(completed_event, None)

        nbr_alarms = idx + 1 - 2
        alarms = collection.get_due_alarms(start)
        self.assertEqual(len(alarms), nbr_alarms)

        for idx, day in enumerate(range(15, 20)):
            start = dt.datetime(2019, 3, day, 17, 0, tzinfo=pytz.UTC)
            with self.subTest(start):
                alarms = collection.get_due_alarms(start)
                self.assertEqual(len(alarms), nbr_alarms + idx + 1)
