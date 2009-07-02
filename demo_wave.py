import numpy as np
#import matplotlib.pyplot as plt
import gtk
import datetime
from matplotlib.figure import Figure
from matplotlib.dates import date2num,num2date,MinuteLocator

# uncomment to select /GTK/GTKAgg/GTKCairo
#from matplotlib.backends.backend_gtk import FigureCanvasGTK as FigureCanvas
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
#from matplotlib.backends.backend_gtkcairo import FigureCanvasGTKCairo as FigureCanvas

from sources import *

class Display(FigureCanvas):
    def __init__(self,par,src):
        self.src = src
        self.click_handler = par
        xb = src.xBounds()
        yb = src.yBounds()
        #print xb
        self.figure = Figure(figsize=(5,4),dpi=100)
        self.plot = self.figure.add_subplot(111,xbound=xb,ybound=yb,autoscale_on=False)
        self.plot.get_xaxis().set_major_locator(MinuteLocator())
        self.plot.plot_date(src.getX(),src.getY(),'-')
        self.spanner = self.plot.axvspan(xb[0],xb[1],alpha=0.5)
        self.ctx_spanners = dict()
        FigureCanvas.__init__(self,self.figure)
        self.mpl_connect('button_press_event',self.on_press)
        self.mpl_connect('button_release_event',self.on_release)
        self.mpl_connect('motion_notify_event',self.on_move)
    def update_range(self,min,max):
        self.plot.set_xlim(min,max)
        self.draw_idle()
    def update_spanner(self,vall,valr):
        if self.spanner != None:
            self.spanner.remove()
            self.spanner = None
        if vall < valr:
            self.spanner = self.plot.axvspan(vall,valr,alpha=0.5)
        self.draw_idle()
    def on_press(self,event):
        if event.xdata != None and event.ydata != None:
            if event.button == 1:
                self.click_handler.bound_change_start(event.xdata)
            elif event.button == 3:
                self.click_handler.select(event.xdata,event.guiEvent.get_time())
    def on_release(self,event):
        if event.xdata != None and event.ydata != None:
            if event.button == 1:
                self.click_handler.bound_change_end(event.xdata)
    def on_move(self,event):
        if event.xdata != None and event.ydata != None:
            self.click_handler.bound_change_update(event.xdata)
    def notice_context(self,descr):
        spans = []
        for (start,end) in descr.entries:
            spans.append(self.plot.axvspan(start,end,alpha=0.3,facecolor=descr.color))
        self.ctx_spanners[descr.name] = spans
    def notice_annotation(self,ctx,col,start,end):
        spans = self.ctx_spanners[ctx]
        spans.append(self.plot.axvspan(start,end,alpha=0.3,facecolor=col))
        self.draw_idle()
    def notice_context_removal(self,ctx):
        ctxd = self.ctx_spanners[ctx]
        for spanner in ctxd:
            spanner.remove()
        del self.ctx_spanners[ctx]
        self.draw_idle()
    def notice_annotation_removal(self,ctx,pos):
        self.ctx_spanners[ctx][pos].remove()
        del self.ctx_spanners[ctx][pos]
        self.draw_idle()

class InputState:
    def __init__(self,par):
        self.bounds = None
        self.tmpl = 0.0
        self.tmpr = 0.0
        self.par = par
        self.bound_change = False
        self.selection = None
    def propagate_marker(self):
        for d in self.par.displays:
            d.update_spanner(self.tmpl,self.tmpr)
    def bound_change_start(self,loc):
        self.tmpl = loc
        self.tmpr = loc
        self.propagate_marker()
        self.bound_change = True
    def bound_change_update(self,loc):
        if self.bound_change:
            self.tmpr = loc
            self.propagate_marker()
    def bound_change_end(self,loc):
        if self.bound_change:
            self.tmpr = loc
            if self.tmpl < self.tmpr:
                self.bounds = (self.tmpl,self.tmpr)
            else:
                self.bounds = None
            self.propagate_marker()
            self.bound_change = False
    def select(self,loc,time):
        if self.bounds != None:
            if loc >= self.bounds[0] and loc <= self.bounds[1]:
                self.selection = True
                self.par.notify_select(time)
                return
        self.selection = self.par.find_annotation(loc)
        self.par.notify_select(time)

class CtxAnnotator(gtk.VBox):
    def __init__(self):
        self.policy = ScaleDisplayPolicy(10000,150)
        self.displays = []
        self.contexts = dict()
        self.context_colors = ['red','green','yellow','orange']
        
        self.display_box = gtk.VBox()
        self.context_box = gtk.HBox()
        self.input_state = InputState(self)
        add_button = gtk.Button(stock='gtk-add')
        add_button.connect('clicked',lambda but: self.create_context())
        self.context_box.pack_start(add_button,expand=False,fill=True)

        scr_win = gtk.ScrolledWindow()
        scr_win.add_with_viewport(self.display_box)
        scr_win.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)

        gtk.VBox.__init__(self)
        self.pack_start(scr_win,expand=True,fill=True)
        self.pack_end(self.context_box,expand=False,fill=True)
        self.connect('key-press-event',self.on_key)
    def on_key(self,wid,ev):
        if ev.string is '+':
            self.bigger()
        elif ev.string is '-':
            self.smaller()
    def find_annotation(self,x):
        for (ctx,but) in self.contexts.values():
            ind = 0
            for ind in range(len(ctx.entries)):
                if ctx.entries[ind][0] <= x and ctx.entries[ind][1] >= x:
                    return (ctx.name,ind)
        return None
    def bigger(self):
        self.policy.biggerx()
        self.update_zoom()
    def smaller(self):
        self.policy.smallerx()
        self.update_zoom()
    def update_zoom(self):
        (w,h) = self.policy.display_sizes(num2date(self.xmax)-num2date(self.xmin))
        for d in self.displays:
            d.set_size_request(w,h)
            
    def recalculate(self):
        xmin = None
        xmax = None
        for d in self.displays:
            min,max = d.src.xBounds()
            if xmin is None or min < xmin:
                xmin = min
            if xmax is None or max > xmax:
                xmax = max
        if not xmin is None:
            for d in self.displays:
                d.update_range(xmin,xmax)
            self.input_state.propagate_marker()

    def add_source(self,src):
        disp = Display(self.input_state,src)
        for ctx in self.contexts:
            disp.notice_context(ctx)
        self.displays.append(disp)
        self.display_box.pack_start(disp,expand=True,fill=True)
        self.recalculate()
    def add_context(self,name):
        found_color = None
        for col in self.context_colors:
            avail = True
            for (ctx,but) in self.contexts.values():
                if ctx.color == col:
                    avail = False
                    break
            if avail:
                found_color = col
                break
        if found_color == None:
            print "HALP! I CAN'T HAZ COLOR!"
            return
        descr = ContextDescription(name,found_color)
        but = ContextButton(descr,self)
        but.show_all()
        self.context_box.pack_start(but,expand=False,fill=True)
        self.contexts[descr.name]=(descr,but)
        for d in self.displays:
            d.notice_context(descr)
    def remove_context(self,name):
        for d in self.displays:
            d.notice_context_removal(name)
        (descr,but) = self.contexts[name]
        self.context_box.remove(but)
        del self.contexts[name]
    def create_context(self):
        dialog = gtk.MessageDialog(None,
                                   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_OK, None)
        dialog.set_markup("Please enter the <b>name</b> of the context")
        entry = gtk.Entry()
        entry.connect("activate", lambda wid: dialog.response(gtk.RESPONSE_OK))
        dialog.vbox.pack_end(entry,expand=True,fill=True)
        dialog.show_all()
        dialog.run()
        self.add_context(entry.get_text())
        dialog.destroy()
    def create_annotation(self,name):
        if self.input_state.bounds != None:
            (start,end) = self.input_state.bounds
            (descr,but) = self.contexts[name]
            descr.entries.append((start,end))
            for d in self.displays:
                d.notice_annotation(name,descr.color,start,end)
    def notify_select(self,time):
        if self.input_state.selection == None:
            pass
        elif self.input_state.selection == True:
            menu = SelectionMenu(self)
            menu.show_all()
            menu.popup(None,None,None,3,time)
        else:
            menu = AnnotationMenu(self)
            menu.show_all()
            menu.popup(None,None,None,3,time)
    def remove_annotation(self,name,pos):
        del self.contexts[name][0].entries[pos]
        for d in self.displays:
            d.notice_annotation_removal(name,pos)

def scale_display(obj,value):
    if value == 0:
        return ""
    else:
        return num2date(value).strftime("%Y-%m-%d %H:%M:%S")

class ScaleDisplayPolicy:
    def __init__(self,pixel_per_hour,base_height=100):
        self.pixel_per_hour = pixel_per_hour
        self.base_height = base_height
        self.scales = [0.25,0.5,1.0,1.5,2.0,2.5,3.0]
        self.curx = 2
        self.cury = 2
    def biggerx(self):
        if self.curx < len(self.scales)-1:
            self.curx += 1
    def smallerx(self):
        if self.curx > 0:
            self.curx -= 1
    def biggery(self):
        if self.cury < len(self.scales)-1:
            self.cury += 1
    def smallery(self):
        if self.cury > 0:
            self.cury -= 1
    def display_sizes(self,tdelta):
        hours = float(tdelta.days)*24.0 + float(tdelta.seconds)/3600
        width = hours*self.pixel_per_hour*self.scales[self.curx]
        height = self.base_height*self.scales[self.cury]
        return (int(width),int(height))

class ContextButton(gtk.HBox):
    def __init__(self,descr,par):
        gtk.HBox.__init__(self)
        add_button = gtk.Button("")
        add_button.get_child().set_markup("<span bgcolor=\""+descr.color+"\">"+descr.name+"</span>")
        rem_button = gtk.Button(stock='gtk-delete')
        self.pack_start(add_button,expand=True,fill=True)
        self.pack_start(rem_button,expand=False,fill=True)
        rem_button.connect('clicked',lambda but: par.remove_context(descr.name))
        add_button.connect('clicked',lambda but: par.create_annotation(descr.name))

class ContextDescription:
    def __init__(self,name,color):
        self.name = name
        self.color = color
        self.entries = []
    def add_entry(self,start,end):
        self.entries.append((start,end))

class SelectionMenu(gtk.Menu):
    def __init__(self,par):
        gtk.Menu.__init__(self)
        ann = gtk.MenuItem(label="Annotate")
        sub_ann = gtk.Menu()
        ann.set_submenu(sub_ann)
        for (ctx,but) in par.contexts.values():
            it = gtk.ImageMenuItem("")
            img = gtk.Image()
            img.set_from_stock(gtk.STOCK_BOLD,gtk.ICON_SIZE_MENU)
            it.set_image(img)
            it.get_child().set_markup("<span bgcolor=\""+ctx.color+"\">"+ctx.name+"</span>")
            it.connect('activate',lambda w,str: par.create_annotation(str),ctx.name)
            sub_ann.append(it)
        sub_ann.append(gtk.SeparatorMenuItem())
        new_it = gtk.ImageMenuItem("New context...")
        new_img = gtk.Image()
        new_img.set_from_stock(gtk.STOCK_ADD,gtk.ICON_SIZE_MENU)
        new_it.set_image(new_img)
        new_it.connect('activate',lambda w: par.create_context())
        sub_ann.append(new_it)
        self.append(ann)

class AnnotationMenu(gtk.Menu):
    def __init__(self,par):
        gtk.Menu.__init__(self)
        it = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        sel = par.input_state.selection
        it.connect('activate',lambda w,name,pos: par.remove_annotation(name,pos),sel[0],sel[1])
        self.append(it)

if __name__=="__main__":
    win = gtk.Window()
    win.connect("destroy", lambda x: gtk.main_quit())

    win.set_default_size(400,300)
    win.set_title("Context Annotator")
    
    box = CtxAnnotator()
    box.add_source(MovementSource("examples/movement.log"))
    cur = datetime.datetime(2009,6,3,11,48,0)

    box.add_source(WaveSource("examples/01 - Elvenpath.wav",cur))
    box.add_context("Blub")
    box.add_context("Blah")
    win.add(box)

    win.show_all()
    gtk.main()
