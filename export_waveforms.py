import os.path as op
import logging
import math
from pyrocko import io
from pyrocko import model
from pyrocko.gui.snuffling import Snuffling, Choice, Switch, Param


logger = logging.getLogger('export')


class ExportWaveforms(Snuffling):
    '''
    <html>
    <head>
    <style type="text/css">
        body { margin-left:10px };
    </style>
    </head>

    <h1 align="center">Export selected or visible traces</h1>
    <body>
    <p>
    Choose the desired format from the <b>Format</b> menu and press
    <b>Run</b>.
    If no traces have been selected using extended markers all traces visible
    in the viewer will be exported.
    </p>
    <p>
    Note that exporting to miniseed requires the network, station, location and
    channel codes to be of length 2, 5, 2 and 3, respectively. Codes exceeding
    these lenghts will be silently truncated.<br />
    In order to have more control on code replacements it is recommended to use
    the command line tool <b>jackseis</b> which is shipped with pyrocko.<br />
    When exporting to miniseed it is possible to combine all traces into
    one file by giving a filename without template placeholders.
    </p>
    </body>
    </html>
    '''

    def setup(self):
        self.set_name('Export Waveforms')
        self.add_parameter(
            Choice(
                'Format', 'format', 'mseed', ['mseed', 'text', 'sac', 'yaff']))

        self.add_parameter(
            Param(
                'Time length limit for output files', 'tinc', None,
                0.1, 86400., low_is_none=True))

        self.add_parameter(Switch('Save Station Meta', 'save_stations', False))
        self.add_parameter(Switch('Apply Filters/Rotation', 'apply_filter', False))
        self.set_live_update(False)

    def call(self):
        self.cleanup()

        if self.tinc is not None:
            template = \
                'trace_%n.%s.%l.%c_%(tmin_us)s'
        else:
            template = 'trace_%n.%s.%l.%c'

        if self.format == 'text':
            default_output_filename = template + '.dat'

        else:
            default_output_filename = template + '.' + self.format

        out_filename = self.output_filename('Template for output files',
                                            default_output_filename)

        viewer = self.get_viewer()
        for trs in self.chopper_selected_traces(fallback=True, tinc=self.tinc):
            traces_save = []
            for tr in trs:
                if self.format == 'mseed':
                    if len(tr.network) > 2:
                        tr.set_network(tr.network[:2])
                    if len(tr.station) > 5:
                        tr.set_station(tr.station[:5])
                    if len(tr.location) > 2:
                        tr.set_location(tr.location[:2])
                    if len(tr.channel) > 3:
                        tr.set_channel(tr.channel[:3])

                if self.apply_filter:
                    if viewer.lowpass is not None and \
                            viewer.highpass is not None:
                        tr.bandpass(2, viewer.highpass, viewer.lowpass)

                    elif viewer.lowpass is not None:
                        if viewer.lowpass < 0.5/tr.deltat:
                            tr.lowpass(4, viewer.lowpass, demean=False)

                    elif viewer.highpass is not None:
                        if viewer.highpass < 0.5/tr.deltat:
                            tr.highpass(4, viewer.highpass, demean=False)


                traces_save.append(tr)

        if viewer.rotate != 0.0 and self.apply_filter:
            phi = viewer.rotate/180.*math.pi
            cphi = math.cos(phi)
            sphi = math.sin(phi)
            for a in traces_save:
                for b in traces_save:
                    if (a.network == b.network
                            and a.station == b.station
                            and a.location == b.location
                            and ((a.channel.lower().endswith('n')
                                 and b.channel.lower().endswith('e'))
                                 or (a.channel.endswith('1')
                                     and b.channel.endswith('2')))
                            and abs(a.deltat-b.deltat) < a.deltat*0.001
                            and abs(a.tmin-b.tmin) < a.deltat*0.01 and
                            a.get_ydata().size == b.get_ydata().size):

                        aydata = a.get_ydata()*cphi+b.get_ydata()*sphi
                        bydata = -a.get_ydata()*sphi+b.get_ydata()*cphi
                        a.set_ydata(aydata)
                        b.set_ydata(bydata)

        try:
            io.save(
                traces_save, out_filename,
                format=self.format,
                overwrite=True)

        except io.io_common.FileSaveError as e:
            self.fail(str(e))

        logger.info('saved waveforms to %s', out_filename)

        if self.save_stations:
            stations = viewer.stations.values()
            fn = self.output_filename('Save Stations', 'stations.pf')
            model.dump_stations(list(stations), fn)
            logger.info('saved stations to %s', fn)


def __snufflings__():
    return [ExportWaveforms()]
