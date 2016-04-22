#! /usr/bin/env python 

from __future__ import print_function, division, unicode_literals
from builtins import range

import sys
import os
from itertools import cycle
import traceback

# Qt4 bindings for core Qt functionalities (non-GUI)
from PyQt4 import QtCore

# Python Qt4 bindings for GUI objects
from PyQt4 import QtGui
from PyQt4.QtCore import Qt

from numpy import (array, zeros, nanmax, nanmin, where, isfinite,
                   argsort, r_)

# import the MainWindow widget from the converted .ui files
from qtplaskin.mainwindow import Ui_MainWindow
from qtplaskin.modeldata import HDF5Data, RealtimeData, DirectoryData, OldDirectoryData

#import publib

try:
    from mpldatacursor import datacursor
    CURSOR = True
except:
    CURSOR = False
    
COLOR_SERIES = ["#5555ff", "#ff5555", "#909090",
                "#ff55ff", "#008800", "#8d0ade",
                "#33bbcc", "#000000", "#444400",
                "#7777ff", "#77ff77"]
LINE_WIDTH = 1.7

# We do not plot densities or rates below these thresholds
DENS_THRESHOLD = 1e-10
RATE_THRESHOLD = 1e-20

CONDITIONS_PRETTY_NAMES = {
            'gas_temperature':
            "Gas temperature [K]",
            'Tgas_K':
            "Gas temperature [K]",
            'reduced_frequency':
            "Reduced frequency cm$^\mathdefault{3}$s$^\mathdefault{-1}$",
            'reduced_field':
            "Reduced field E/N [Td]",
            'E/N_Td':
            "Reduced field E/N [Td]",
            'elec_temperature':
            "Electron temperature [K]",
            'Telec_K':
            "Electron temperature [K]",
            'elec_drift_velocity':
            "Electron drift velocity [cm/s]",
            'elec_diff_coeff':
            "Electron diffusion coeff. [cm$^\mathdefault{2}$s$^\mathdefault{-1}$]",
            'elec_frequency_n':
            "Electron reduced colission freq. [cm$^\mathdefault{3}$s$^\mathdefault{-1}$]",
            'elec_power_n':
            "Electron reduced power [eV cm$^\mathdefault{3}$s$^\mathdefault{-1}$]",
            'elec_power_elastic_n':
            "Electron reduced elastic power [eV cm$^\mathdefault{3}$s$^\mathdefault{-1}$]",
            'elec_power_inelastic_n':
            "Electron reduced inelastic power [eV cm$^\mathdefault{3}$s$^\mathdefault{-1}$]"}

class DesignerMainWindow(QtGui.QMainWindow, Ui_MainWindow):
    """Customization for Qt Designer created window"""
    def __init__(self, parent = None):
        # initialization of the superclass
        super(DesignerMainWindow, self).__init__(parent)
        # setup the GUI --> function generated by pyuic4
        self.setupUi(self)

        # In some lists we can select more than one item
        self.speciesList.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection)
        self.reactList.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection)

        for w in [self.reactList, self.speciesList, self.speciesSourceList,
                  self.condList]:
            w.horizontalHeader().setVisible(True)

        self.plot_widgets = [self.condWidget,
                             self.densWidget,
                             self.reactWidget,
                             self.sourceWidget]
        
        self.update_timer = QtCore.QTimer()
        self.latest_dir = "."

        # connect the signals with the slots
        QtCore.QObject.connect(self.condButton, 
                               QtCore.SIGNAL("clicked()"),
                               self.update_cond_graph)

        QtCore.QObject.connect(self.plotButton, 
                               QtCore.SIGNAL("clicked()"),
                               self.update_spec_graph)

        QtCore.QObject.connect(self.sourceButton, 
                               QtCore.SIGNAL("clicked()"),
                               self.update_source_graph)

        QtCore.QObject.connect(self.reactButton, 
                               QtCore.SIGNAL("clicked()"),
                               self.update_react_graph)

        QtCore.QObject.connect(self.actionOpen, 
                               QtCore.SIGNAL('triggered()'),
                               self.select_file)

        QtCore.QObject.connect(self.actionStart_a_simulation, 
                               QtCore.SIGNAL('triggered()'),
                               self.start_a_simulation)

        QtCore.QObject.connect(self.actionImport_from_directory, 
                               QtCore.SIGNAL('triggered()'),
                               self.import_from_directory)

        QtCore.QObject.connect(self.actionUpdate, 
                               QtCore.SIGNAL('triggered()'),
                               self.data_update)

        QtCore.QObject.connect(self.actionExport_data, 
                               QtCore.SIGNAL('triggered()'),
                               self.export_data)

        QtCore.QObject.connect(self.actionSave, 
                               QtCore.SIGNAL('triggered()'),
                               self.save_to_file)

        QtCore.QObject.connect(self.actionLog_scale_in_time, 
                               QtCore.SIGNAL('triggered()'),
                               self.action_set_logtime)

        QtCore.QObject.connect(self.actionQuit, 
                               QtCore.SIGNAL('triggered()'), 
                               QtGui.qApp, QtCore.SLOT("quit()"))
    
        QtCore.QObject.connect(self.update_timer,
                               QtCore.SIGNAL("timeout()"),
                               self.data_update)

    def datacursor(self,line):
        ''' Return datacursor'''
        if CURSOR:
            return datacursor(line,hover=True,size=14,color='k', 
                                    bbox=dict(fc='white',alpha=0.9)) 
        else:
            return None

    # Drag'n'Drop.  Implemented by Marc Foletto.
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # Drag'n'Drop.
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fname = url.toLocalFile()
                self.import_file_or_dir(fname)

            event.acceptProposedAction()
                            

    #Chose if drop is a file or a directory
    def import_file_or_dir(self, path):
        if os.path.exists(path):
            if os.path.isdir(path):
                self._import_from_directory(path)
            else:
                # Let us allow the user to import files with any extension:
                # if they are not in hdf5 format and exception will be raised
                # anyhow.
                self.load_h5file(path)


    def set_location(self, location):
        """ Sets the opened location. """
        self.setWindowTitle("%s - QtPlaskin" % location)
        self.location = location

    @property
    def xscale(self):
        if self.actionLog_scale_in_time.isChecked():
            return 'log'
        else:
            return 'linear'
        
    def update_cond_graph(self):
        """Updates the graph with conditions"""

        try:
            condition = list(iter_2_selected(self.condList))[0][0]
        except AttributeError:
            return

        # clear the Axes
        if not self.condWidget.axes:
            self.condWidget.init_axes()
        else:
            self.condWidget.clear()

        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        
        y = array(self.data.condition(condition))
        condition_name = self.data.conditions[condition - 1]

        flt = y > 0
        label = CONDITIONS_PRETTY_NAMES.get(condition_name, condition_name)
        self.condWidget.axes[0].plot(self.data.t[flt], y[flt], lw=LINE_WIDTH,
                                     label=label,
                                     zorder=10)

        self.condWidget.set_scales(yscale='linear', xscale=self.xscale)
        self.condWidget.axes[0].set_xlabel("t [s]")
        self.condWidget.axes[0].set_ylabel(label)

        # force an image redraw
        self.condWidget.draw()
        
        self.condWidget.add_data(self.data.t, y, label)
        QtGui.QApplication.restoreOverrideCursor()


    def update_spec_graph(self):
        """Updates the graph with densities"""
        # clear the Axes
        if not self.speciesList.selectedItems():
            return

        if not self.densWidget.axes:
            self.densWidget.init_axes()
        else:
            self.densWidget.clear()

        
        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        self.data.flush()
        citer = cycle(COLOR_SERIES)
        
        lines = []
        for item in iter_2_selected(self.speciesList):
            name = item[1]
            dens = self.data.density(item[0])
            flt = dens > DENS_THRESHOLD
            lines.append(self.densWidget.axes[0].plot(self.data.t[flt], dens[flt],
                                         lw=LINE_WIDTH,
                                         c=next(citer), label=name,
                                         zorder=10)[0])
            self.densWidget.add_data(self.data.t, dens, name)
        self.datacursor(lines) 

        self.densWidget.set_scales(yscale='log', xscale=self.xscale)
        self.densWidget.axes[0].set_xlabel("t [s]")
        self.densWidget.axes[0].set_ylabel("Density [cm$^\mathdefault{-3}$]")
        self.densWidget.axes[0].legend(loc=(1.05, 0.0), prop=dict(size=11))

        # force an image redraw
        self.densWidget.draw()

        QtGui.QApplication.restoreOverrideCursor()


    def update_source_graph(self):
        """Updates the graph with sources rates"""
        try:
            species = list(iter_2_selected(self.speciesSourceList))[0]
        except AttributeError:
            return
        
        # clear the Axes
        if not self.sourceWidget.axes:
            self.sourceWidget.init_axes()
        else:
            self.sourceWidget.clear()

        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        
        dreactions = self.data.sources(species[0])
        reactions = list(dreactions.keys())
        
        r = zeros((len(reactions), len(self.data.t)))
        for i, react in enumerate(reactions):
            r[i, :] = dreactions[react]
            
        # Find the reactions that are at some point at least a delta of the total
        filters = {0: (0.1, -1),
                   1: (0.01, -1),
                   2: (0.001, -1),
                   3: (1e-4, -1),
                   4: (0.0, -1)}
        
        delta, max_rates = filters[self.Combo_filter.currentIndex()]

        spos = nanmax(where(r > 0, r, 0), axis=0)
        fpos = r // spos

        # This is b.c. numpy does not provide a nanargsort
        fpos = where(isfinite(fpos), fpos, 0)
        
        sneg = nanmin(where(r < 0, r, 0), axis=0)
        fneg = r // sneg
        
        # This is b.c. numpy does not provide a nanargsort
        fneg = where(isfinite(fneg), fneg, 0)

        icreation = select_rates(fpos, delta, max_rates=max_rates)
        idestruct = select_rates(fneg, delta, max_rates=max_rates)

        citer = cycle(COLOR_SERIES)
        lines = []
        for i in icreation:
            name = self.data.reactions[reactions[i]]
            flt = abs(r[i, :]) > RATE_THRESHOLD
            label = "[%d] %s" % (reactions[i] + 1, name)

            lines.append(self.sourceWidget.creationAx.plot(self.data.t[flt],
                                              abs(r[i, flt]),
                                              c=next(citer),
                                              lw=LINE_WIDTH,
                                              label=label,
                                              zorder=10)[0])

            self.sourceWidget.add_data(self.data.t, r[i, :], label)

        citer = cycle(COLOR_SERIES)
        for i in idestruct:
            name = self.data.reactions[reactions[i]]
            flt = abs(r[i, :]) > RATE_THRESHOLD
            label = "[%d] %s" % (reactions[i] + 1, name)

            lines.append(self.sourceWidget.removalAx.plot(self.data.t[flt],
                                             abs(r[i, flt]),
                                             c=next(citer),
                                             lw=LINE_WIDTH,
                                             label=label,
                                             zorder=10))

            self.sourceWidget.add_data(self.data.t, r[i, :], "- " + label)

#        self.datacursor(lines)

        self.sourceWidget.creationAx.set_ylabel(
            "Production [cm$^\mathdefault{-3}$s$^\mathdefault{-1}$]")
        self.sourceWidget.creationAx.legend(loc=(1.05, 0.0),
                                            prop=dict(size=9))


        self.sourceWidget.removalAx.set_ylabel(
            "Losses [cm$^\mathdefault{-3}$s$^\mathdefault{-1}$]")
        self.sourceWidget.removalAx.set_xlabel("t [s]")

        self.sourceWidget.removalAx.legend(loc=(1.05, 0.0),
                                           prop=dict(size=9))

        
        self.sourceWidget.set_scales(yscale='log', xscale=self.xscale)

        # force an image redraw
        self.sourceWidget.draw()

        QtGui.QApplication.restoreOverrideCursor()


    def update_react_graph(self):
        """Updates the graph with reaction rates"""
        if not self.reactList.selectedItems():
            return

        # clear the Axes
        if not self.reactWidget.axes:
            self.reactWidget.init_axes()
        else:
            self.reactWidget.clear()

        QtGui.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))

        citer = cycle(COLOR_SERIES)
        lines = []
        for item in iter_2_selected(self.reactList):
            name = item[1]
            rate = array(self.data.rate(item[0]))
            
            flt = rate > RATE_THRESHOLD
            label = "[%d] %s" % (item[0], name)

            lines.append(self.reactWidget.axes[0].plot(self.data.t[flt], rate[flt],
                                          c=next(citer),
                                          lw=LINE_WIDTH,
                                          label=label,
                                          zorder=10)[0])
            self.reactWidget.add_data(self.data.t, rate, label)
        self.datacursor(lines) 

        self.reactWidget.set_scales(yscale='log', xscale=self.xscale)
            
        self.reactWidget.axes[0].set_xlabel("t [s]")
        self.reactWidget.axes[0].set_ylabel(
            "Rate [cm$^\mathdefault{-3}$s$^\mathdefault{-1}$]")
        self.reactWidget.axes[0].legend(loc=(1.025, 0.0),
                                        prop=dict(size=8))

        # force an image redraw
        self.reactWidget.draw()

        QtGui.QApplication.restoreOverrideCursor()



    def select_file(self):
        """opens a file select dialog"""
        # open the dialog and get the selected file
        file = QtGui.QFileDialog.getOpenFileName(self, "Open data file",
                                                 ".",
                                                 "HDF5 files (*.h5 *.hdf5);;"
                                                 "All files (*)")
        # if a file is selected
        if file:
            try:
                self.load_h5file(file)
                self.set_location(file)

                self.update_lists()
                self.clear()

            except IOError as e:
                QtGui.QErrorMessage(self).showMessage(
                    "Failed to open file.  Incorrect format? <%s>" % e)
                

    def start_a_simulation(self):
        self.data = RealtimeData('fpr_1', 'init_species.dat',
                                 'field_constant.tsv',
                                 max_dt=10e-3)
        self.update_lists()


    def import_from_directory(self):
        fname = QtGui.QFileDialog.getExistingDirectory(
            self, "Import data from directory",
            self.latest_dir, QtGui.QFileDialog.ShowDirsOnly)
        
        self._import_from_directory(fname)
        self.latest_dir = fname

    def _import_from_directory(self, fname):
        try:
            try:
                self.data = DirectoryData(fname)
            except IOError as e:
                em = QtGui.QErrorMessage(self)
                em.setModal(True)
                em.showMessage(
                    ("Failed to open directory (%s).\n" % str(e))
                    + "I will try now to import files in deprecated format.")
                # If we do not call exec_ here, two dialogs may appear at
                # the same time, confusing the user.
                em.exec_()
                self.data = OldDirectoryData(fname)

            self.set_location(fname)
            self.update_lists()
            self.clear()
        except IOError as e:
            em = QtGui.QErrorMessage(self)
            em.setModal(True)
            em.exec_()
            em.showMessage(
                "Failed to open directory (%s).\n" % str(e))
                

    def data_update(self):
        self.data.update()
        
        self.update_cond_graph()
        self.update_spec_graph()
        self.update_source_graph()
        self.update_react_graph()
        
    
    def save_to_file(self):
        """opens a file select dialog"""
        # open the dialog and get the selected file
        fname = QtGui.QFileDialog.getSaveFileName(self, "Save to file",
                                                  ".",
                                                  "HDF5 files (*.h5 *.hdf5);;"
                                                  "All files (*)")

        # if a file is selected
        if fname:
            self.data.save(fname)
    

    def export_data(self):
        """opens a file select dialog"""
        # open the dialog and get the selected file
        fname = QtGui.QFileDialog.getSaveFileName(self, "Export data to file",
                                                  ".",
                                                  "TSV files (*.tsv);;"
                                                  "TXT files (*.txt);;"
                                                  "DAT files (*.dat);;"
                                                  "All files (*)")

        # if a file is selected
        if fname:
            fname = fname
            self.plot_widgets[self.tabWidget.currentIndex()]\
                .savedata(fname, self.location)
        
            
    def action_set_logtime(self):
        for w in self.plot_widgets:
            w.set_scales(xscale=self.xscale, redraw=True)

    def load_h5file(self, file):
        self.data = HDF5Data(file)
        self.update_lists()
        self.clear()
        

    def update_lists(self):

        #self.species = sorted(self.data.species)
        #self.reactions = sorted(self.data.reactions)
        #self.conditions = sorted(self.data.conditions)

        def _populate(qtable, list, pretty_names={}):
            for i in range(qtable.rowCount()):
                qtable.removeRow(0)
                
            for n, item in enumerate(list):
                row = qtable.rowCount()
                qtable.insertRow(row)
                # The + 1 is to move to the FORTRAN/ZdPlaskin convention
                nitem = QtGui.QTableWidgetItem(u'%4d' % (n + 1))
                nitem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                nitem.setTextColor(QtGui.QColor(160, 160, 160))
                qtable.setItem(row, 0, nitem)
                
                showed_item = pretty_names.get(item, item)
                sitem = QtGui.QTableWidgetItem(showed_item)
                sitem.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                qtable.setItem(row, 1, sitem)

        _populate(self.speciesList, self.data.species)
        _populate(self.speciesSourceList, self.data.species)
        _populate(self.reactList, self.data.reactions)
        _populate(self.condList, self.data.conditions,
                  pretty_names=CONDITIONS_PRETTY_NAMES)

        
    def clear(self):
        for w in self.plot_widgets:
            w.clear()
        
        
    def parse_file(self, filename):
        pass


def select_rates(f, delta, max_rates=4, min_rates=0):
    fmax = nanmax(f, axis=1)
    
    asort = argsort(-fmax)
    n = len(asort)

    # We always select at least the highest min_rates.
    highest = asort[:min_rates]

    # if n < max_rates:
    #    return highest

    # From the rest, we select those larger than delta, but not more
    # than max_rates
    p = asort[min_rates:max_rates]
    rest = p[fmax[p] > delta]
    
    if n == max_rates:
        return r_[highest, rest]

    # We should never leave aside rates that at some point are very
    # important, even if they fall outside max_rates
    p = asort[max_rates:]
    rest2 = p[fmax[p] > (1 - delta)]
    return r_[highest, rest, rest2]
    

def iter_2_selected(qtablewidget):
    selectedRanges = qtablewidget.selectedRanges()

    selected = []
    for r in selectedRanges:
        bottom, top = r.bottomRow(), r.topRow()
        for i in range(top, bottom + 1):
            itemId = qtablewidget.item(i, 0)
            itemStr = qtablewidget.item(i, 1)
            selected.append((int(itemId.text()), str(itemStr.text())))

    return selected
        


# create the GUI application
app = QtGui.QApplication(sys.argv)

# instantiate the main window
dmw = DesignerMainWindow()

# Load file if present in sys.argv
if(len(sys.argv) >1):
    fname=sys.argv[1]
    dmw.import_file_or_dir(fname)

# show it
dmw.show()
dmw.raise_()

def new_excepthook(type, value, tb):
    em = QtGui.QErrorMessage(dmw)
    em.setModal(True)
    msg = "An unhandled exception was raised:\n"
    em.showMessage(msg + '&#xa;<br>'.join(traceback.format_exception(type, value, tb)))
    # If we do not call exec_ here, two dialogs may appear at
    # the same time, confusing the user.
    em.exec_()

sys.excepthook = new_excepthook

# start the Qt main loop execution, exiting from this script
# with the same return code of Qt application
sys.exit(app.exec_())
