import os
import shutil
import pathlib
import itertools
import csv
import zipfile
import pcbnew  # https://docs.kicad.org/doxygen-python-7.0/namespacepcbnew.html
import wx  # https://docs.wxpython.org/wx.functions.html

class InputLabsExport(pcbnew.ActionPlugin):
    def Run(self):
        self.board = pcbnew.GetBoard()
        project_file = pathlib.Path(self.board.GetFileName())
        self.project_folder = project_file.parent
        self.output_folder = self.project_folder / 'order'
        self.temp_folder = self.project_folder / 'order/temp'
        self.log_init()

    def log_init(self):
        self.log_file = self.project_folder / 'plugins/kicad_log'
        if self.log_file.exists():
            os.remove(self.log_file)

    def log(self, *msg):
        with open(self.log_file, 'a') as file:
            if len(msg) == 1: msg = msg[0]
            file.write(f'{msg}\n')

    def delete_temp(self):
        shutil.rmtree(self.temp_folder, ignore_errors=True)

    def export_plot(self):
        plot_controller = pcbnew.PLOT_CONTROLLER(self.board)
        plot_options = plot_controller.GetPlotOptions()
        plot_options.SetOutputDirectory(self.temp_folder)
        # General options.
        plot_options.SetPlotFrameRef(False)
        plot_options.SetPlotValue(False)
        plot_options.SetPlotReference(True)
        plot_options.SetPlotInvisibleText(False)
        # plot_options.SetExcludeEdgeLayer(True)  # Deprecated ?
        plot_options.SetSketchPadsOnFabLayers(False)
        plot_options.SetUseAuxOrigin(False)
        plot_options.SetAutoScale(True)
        plot_options.SetMirror(False)
        plot_options.SetNegative(False)
        # Gerber options.
        plot_options.SetUseGerberProtelExtensions(True)
        plot_options.SetCreateGerberJobFile(False)
        plot_options.SetSubtractMaskFromSilk(True)
        plot_options.SetIncludeGerberNetlistInfo(False)
        # Plot.
        layers = {
            'F.Cu': pcbnew.F_Cu,
            'B.Cu': pcbnew.B_Cu,
            'F.Paste': pcbnew.F_Paste,
            'B.Paste': pcbnew.B_Paste,
            'F.Silkscreen': pcbnew.F_SilkS,
            'B.Silkscreen': pcbnew.B_SilkS,
            'F.Mask': pcbnew.F_Mask,
            'B.Mask': pcbnew.B_Mask,
            'Edge.Cuts': pcbnew.Edge_Cuts,
        }
        for name, layer in layers.items():
            plot_controller.SetLayer(layer)
            plot_controller.OpenPlotfile(name, pcbnew.PLOT_FORMAT_GERBER, name)
            plot_controller.PlotLayer()
        plot_controller.ClosePlot()

    def export_drill(self):
        writer = pcbnew.EXCELLON_WRITER(self.board)
        writer.SetRouteModeForOvalHoles(False)
        writer.SetFormat(
            True,  # aMetric
            pcbnew.GENDRILL_WRITER_BASE.DECIMAL_FORMAT,  # aZerosFmt
            3,  # aLeftDigits
            3,  # aRightDigits
        )
        writer.SetOptions(
            False,  # aMirror.
            False,  # aMinimalHeader
            writer.GetOffset(),  # aOffset.
            False,  # aMerge_PTH_NPTH
        )
        writer.CreateDrillandMapFilesSet(
            str(self.temp_folder),  # aPlotDirectory
            True,   # aGenDrill
            False,  # aGenMap
            None,   # aReporter
        )


class InputLabsExportJLCPCB(InputLabsExport):
    def defaults(self):
        self.name = "Input Labs: JLCPCB export"
        self.category = "Export"
        self.description = "Export plot and drill files"
        self.show_toolbar_button = False

    def Run(self):
        super(InputLabsExportJLCPCB, self).Run()
        self.prepare_folders()
        self.export_plot()
        self.export_drill()
        self.zip_gerber()
        self.delete_temp()
        self.export_cpl()
        self.export_bom()
        msg = (
            'Production files successfully created at:\n' +
            str(self.output_folder)
        )
        wx.MessageBox(msg, self.name, wx.OK)

    def prepare_folders(self):
        self.delete_temp()
        if not self.output_folder.exists():
            os.makedirs(self.output_folder)
        for path in self.output_folder.glob('jlcpcb_*'):
            os.remove(path)

    def get_footprints(self):
        footprints = self.board.GetFootprints()
        def is_exportable(footprint):
            if not footprint.HasProperty('LCSC'): return False
            if footprint.GetProperty('LCSC') == '': return False
            truthly = ['True', 'true', 'TRUE', 'Yes', 'yes', 'YES', '1']
            if footprint.GetProperty('Export') not in truthly: return False
            return True
        return filter(is_exportable, footprints)

    def export_cpl(self):
        fields = ['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation']
        cpl_file = self.output_folder / 'jlcpcb_cpl.csv'
        writer = csv.DictWriter(open(cpl_file, 'w'), fieldnames=fields)
        writer.writeheader()
        footprints = self.get_footprints()
        for footprint in sorted(footprints, key=lambda x: x.GetReference()):
            position_x, position_y = footprint.GetPosition()
            writer.writerow({
                'Designator': footprint.GetReference(),
                'Mid X': position_x /  1000000,
                'Mid Y': position_y / -1000000,
                'Layer': 'bottom' if footprint.IsFlipped() else 'top',
                'Rotation': int(footprint.GetOrientation().AsDegrees()),
            })

    def export_bom(self):
        fields = ['Comment', 'Designator', 'Footprint', 'LCSC Part Number']
        bom_file = self.output_folder / 'jlcpcb_bom.csv'
        writer = csv.DictWriter(open(bom_file, 'w'), fieldnames=fields)
        writer.writeheader()
        footprints = sorted(
            self.get_footprints(),
            key=lambda x: x.GetProperty('LCSC')
        )
        groups = itertools.groupby(footprints, lambda x: x.GetProperty('LCSC'))
        for lcsc, group in groups:
            if not lcsc: continue
            group = list(group)  # Making a reusable copy.
            references = [x.GetReference() for x in group]
            comment = group[0].GetPropertyNative('Group')
            mount = group[0].GetProperty('Mount')
            writer.writerow({
                'Comment': comment,
                'Designator': ','.join(sorted(references)),
                'Footprint': mount,
                'LCSC Part Number': lcsc,
            })

    def zip_gerber(self):
        zip_path = self.output_folder / 'jlcpcb_gerber.zip'
        zipper = zipfile.ZipFile(
            zip_path,
            mode='w',
            compression=zipfile.ZIP_DEFLATED,
        )
        for path in self.temp_folder.glob('*'):
            zipped_path = path.relative_to(self.temp_folder)
            zipped_path = zipped_path.with_name(
                zipped_path.name.replace('alpaca', 'board')
            )
            zipper.write(path, zipped_path)


InputLabsExportJLCPCB().register()
