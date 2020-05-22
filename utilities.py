from decimal import Decimal
import math
import datetime
import calendar

import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
import tkinter.scrolledtext as tkst

FIELD_TYPE_ANGLE = 'angle'
FIELD_TYPE_FLOAT = 'float'
FIELD_TYPE_NUMBER = 'number'


def average_coordinates(coord_list_1, coord_list_2):
    average_easting = (coord_list_1[0] + coord_list_2[0]) / 2.0
    average_northing = (coord_list_1[1] + coord_list_2[1]) / 2.0
    average_elevation = (coord_list_1[2] + coord_list_2[2]) / 2.0

    return [average_easting, average_northing, average_elevation]


def decimalize_value(in_value, precision):
    if precision == '4dp':
        return Decimal(in_value).quantize(Decimal('1.0000'))
    else:
        return Decimal(in_value).quantize(Decimal('1.000'))


def rad2deg(radians):
    degrees = 180 * radians / math.pi
    return degrees


def deg2rad(degrees):
    radians = math.pi * degrees / 180
    return radians


def angle_decimal2DMS(in_deg):
    min, sec = divmod(in_deg * 3600, 60)
    deg, min = divmod(min, 60)

    return '{0:03d}'.format(int(deg)) + '{0:02d}'.format(int(min)) + '{0:02d}'.format(int(sec))


def angle_DMS_2_decimal(angle_deg, angle_min, angle_sec):
    # str_value = str(angle_deg) + '.' + '{:.3f}'.format(float(angle_min)/60) + '{:.3f}'.format(float(angle_sec)/3600)
    return float(angle_deg) + float(angle_min) / 60 + float(angle_sec) / (60 * 60)


def angular_difference(angle_1, angle_2, angle):
    rad_a = deg2rad(angle_1)
    rad_b = deg2rad(angle_2)
    if angle == 180:
        rad_diff = max([rad_a, rad_b]) - min([rad_a, rad_b])
        angular_diff = abs(angle - rad2deg(rad_diff))
    else:
        rad_diff = rad_a + rad_b
        angular_diff = abs(angle - rad2deg(rad_diff))
    return round(angular_diff, 6)


def get_time_differance(time1, time2):
    time1_list = time1.split(':')
    time2_list = time2.split(':')

    hrs1 = int(time1_list[0])
    min1 = int(time1_list[1])

    hrs2 = int(time2_list[0])
    min2 = int(time2_list[1])

    time_diff_hr = '{0:02d}'.format(hrs2 - hrs1)
    time_diff_mins = '{0:02d}'.format(min2 - min1)

    return time_diff_hr + ':' + time_diff_mins


def get_numerical_value_from_string(str_value, field_type, precision='3dp'):
    if field_type == FIELD_TYPE_NUMBER:
        return int(str_value)
    elif field_type == FIELD_TYPE_ANGLE:
        # e.g '035° 13\' 27"'
        angle_list = str_value.split()
        angle_deg = angle_list[0].replace('°', '')
        angle_min = angle_list[1].replace('\'', '')
        angle_sec = angle_list[2].replace('\"', '')

        return angle_DMS_2_decimal(angle_deg, angle_min, angle_sec)

    elif field_type == FIELD_TYPE_FLOAT:
        return decimalize_value(float(str_value), precision) if str_value != "" else ""


def get_calendar(locale, fwday):
    # instantiate proper calendar class
    if locale is None:
        return calendar.TextCalendar(fwday)
    else:
        return calendar.LocaleTextCalendar(fwday, locale)


class CustomDialogBox:

    def __init__(self, master, msg):
        super().__init__()

        self.top = tk.Toplevel(master)
        self.top.title = "TITLE"

        self.top = tk.Toplevel(master)
        self.top.title = "TITLE"
        self.frame = tk.Frame(self.top, bg='orange')

        self.frame.pack(fill='both', expand='yes')
        self.scrolled_text = tkst.ScrolledText(
            master=self.frame,
            wrap='word',  # wrap text at full words only
            # width=70,  # characters
            # height=30,  # text lines
        )

        # the padx/pady space will form a frame
        self.scrolled_text.pack(fill='both', expand=True, ipadx=2, ipady=2, padx=2, pady=2)
        self.scrolled_text.insert('insert', msg)

        master.wait_window(self.top)


class Today:
    todays_date = datetime.datetime.today().strftime('%y%m%d')
    # todays_date = '200414'
    todays_day = todays_date[-2:]
    todays_month = todays_date[-4:-2]
    todays_year = todays_date[-6:-4]
    todays_date_reversed = todays_day + todays_month + todays_year
    todays_date_month_day_format = todays_month + todays_day


class Calendar(ttk.Frame):
    datetime = calendar.datetime.datetime
    timedelta = calendar.datetime.timedelta

    def __init__(self, master=None, **kw):
        """
        WIDGET-SPECIFIC OPTIONS

            locale, firstweekday, year, month, selectbackground,
            selectforeground
        """
        # remove custom options from kw before initializating ttk.Frame
        fwday = kw.pop('firstweekday', calendar.MONDAY)
        year = kw.pop('year', self.datetime.now().year)
        month = kw.pop('month', self.datetime.now().month)
        locale = kw.pop('locale', None)
        sel_bg = kw.pop('selectbackground', '#ecffc4')
        sel_fg = kw.pop('selectforeground', '#05640e')

        self._date = self.datetime(year, month, 1)
        self._selection = None  # no date selected

        ttk.Frame.__init__(self, master, **kw)

        self._cal = get_calendar(locale, fwday)

        self.__setup_styles()  # creates custom styles
        self.__place_widgets()  # pack/grid used widgets
        self.__config_calendar()  # adjust calendar columns and setup tags
        # configure a canvas, and proper bindings, for selecting dates
        self.__setup_selection(sel_bg, sel_fg)

        # store items ids, used for insertion later
        self._items = [self._calendar.insert('', 'end', values='')
                       for _ in range(6)]
        # insert dates in the currently empty calendar
        self._build_calendar()

        # set the minimal size for the widget
        self._calendar.bind('<Map>', self.__minsize)

    def __setitem__(self, item, value):
        if item in ('year', 'month'):
            raise AttributeError("attribute '%s' is not writeable" % item)
        elif item == 'selectbackground':
            self._canvas['background'] = value
        elif item == 'selectforeground':
            self._canvas.itemconfigure(self._canvas.text, item=value)
        else:
            ttk.Frame.__setitem__(self, item, value)

    def __getitem__(self, item):
        if item in ('year', 'month'):
            return getattr(self._date, item)
        elif item == 'selectbackground':
            return self._canvas['background']
        elif item == 'selectforeground':
            return self._canvas.itemcget(self._canvas.text, 'fill')
        else:
            r = ttk.tclobjs_to_py({item: ttk.Frame.__getitem__(self, item)})
            return r[item]

    def __setup_styles(self):
        # custom ttk styles
        style = ttk.Style(self.master)
        arrow_layout = lambda dir: (
            [('Button.focus', {'children': [('Button.%sarrow' % dir, None)]})]
        )
        style.layout('L.TButton', arrow_layout('left'))
        style.layout('R.TButton', arrow_layout('right'))

    def __place_widgets(self):
        # header frame and its widgets
        hframe = ttk.Frame(self)
        lbtn = ttk.Button(hframe, style='L.TButton', command=self._prev_month)
        rbtn = ttk.Button(hframe, style='R.TButton', command=self._next_month)
        self._header = ttk.Label(hframe, width=15, anchor='center')
        # the calendar
        self._calendar = ttk.Treeview(show='', selectmode='none', height=7)

        # pack the widgets
        hframe.pack(in_=self, side='top', pady=4, anchor='center')
        lbtn.grid(in_=hframe)
        self._header.grid(in_=hframe, column=1, row=0, padx=12)
        rbtn.grid(in_=hframe, column=2, row=0)
        self._calendar.pack(in_=self, expand=1, fill='both', side='bottom')

    def __config_calendar(self):
        cols = self._cal.formatweekheader(3).split()
        self._calendar['columns'] = cols
        self._calendar.tag_configure('header', background='grey90')
        self._calendar.insert('', 'end', values=cols, tag='header')
        # adjust its columns width
        font = tkFont.Font()
        maxwidth = max(font.measure(col) for col in cols)
        for col in cols:
            self._calendar.column(col, width=maxwidth, minwidth=maxwidth,
                                  anchor='e')

    def __setup_selection(self, sel_bg, sel_fg):
        self._font = tkFont.Font()
        self._canvas = canvas = tk.Canvas(self._calendar,
                                          background=sel_bg, borderwidth=0, highlightthickness=0)
        canvas.text = canvas.create_text(0, 0, fill=sel_fg, anchor='w')

        canvas.bind('<ButtonPress-1>', lambda evt: canvas.place_forget())
        self._calendar.bind('<Configure>', lambda evt: canvas.place_forget())
        self._calendar.bind('<ButtonPress-1>', self._pressed)

    def __minsize(self, evt):
        width, height = self._calendar.master.geometry().split('x')
        height = height[:height.index('+')]
        self._calendar.master.minsize(width, height)

    def _build_calendar(self):
        year, month = self._date.year, self._date.month

        # update header text (Month, YEAR)
        header = self._cal.formatmonthname(year, month, 0)
        self._header['text'] = header.title()

        # update calendar shown dates
        cal = self._cal.monthdayscalendar(year, month)
        for indx, item in enumerate(self._items):
            week = cal[indx] if indx < len(cal) else []
            fmt_week = [('%02d' % day) if day else '' for day in week]
            self._calendar.item(item, values=fmt_week)

    def _show_selection(self, text, bbox):
        """Configure canvas for a new selection."""
        x, y, width, height = bbox

        textw = self._font.measure(text)

        canvas = self._canvas
        canvas.configure(width=width, height=height)
        canvas.coords(canvas.text, width - textw, height / 2 - 1)
        canvas.itemconfigure(canvas.text, text=text)
        canvas.place(in_=self._calendar, x=x, y=y)

    # Callbacks

    def _pressed(self, evt):
        """Clicked somewhere in the calendar."""
        x, y, widget = evt.x, evt.y, evt.widget
        item = widget.identify_row(y)
        column = widget.identify_column(x)

        if not column or not item in self._items:
            # clicked in the weekdays row or just outside the columns
            return

        item_values = widget.item(item)['values']
        if not len(item_values):  # row is empty for this month
            return

        text = item_values[int(column[1]) - 1]
        if not text:  # date is empty
            return

        bbox = widget.bbox(item, column)
        if not bbox:  # calendar not visible yet
            return

        # update and then show selection
        text = '%02d' % text
        self._selection = (text, item, column)
        self._show_selection(text, bbox)

    def _prev_month(self):
        """Updated calendar to show the previous month."""
        self._canvas.place_forget()

        self._date = self._date - self.timedelta(days=1)
        self._date = self.datetime(self._date.year, self._date.month, 1)
        self._build_calendar()  # reconstuct calendar

    def _next_month(self):
        """Update calendar to show the next month."""
        self._canvas.place_forget()

        year, month = self._date.year, self._date.month
        self._date = self._date + self.timedelta(
            days=calendar.monthrange(year, month)[1] + 1)
        self._date = self.datetime(self._date.year, self._date.month, 1)
        self._build_calendar()  # reconstruct calendar

    # Properties

    @property
    def selection(self):
        """Return a datetime representing the current selected date."""
        if not self._selection:
            return None

        year, month = self._date.year, self._date.month
        return self.datetime(year, month, int(self._selection[0]))


def test():
    import sys
    root = tk.Tk()
    root.title('Ttk Calendar')
    ttkcal = Calendar(firstweekday=calendar.SUNDAY)
    ttkcal.pack(expand=1, fill='both')

    if 'win' not in sys.platform:
        style = ttk.Style()
        style.theme_use('clam')

    root.mainloop()


if __name__ == '__main__':
    test()
