import sys
import time
import math
import os
import vtk
import PyQt5.QtWidgets as QtWidgets
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

# default brain settings
APPLICATION_TITLE = "Theia – NIfTI (nii.gz) 3D Visualizer"
BRAIN_THRESHOLD = 20
BRAIN_SMOOTHNESS = 500
BRAIN_OPACITY = 0.2
BRAIN_COLORS = [(1.0, 0.9, 0.9)]  # RGB percentages

# default tumor settings
TUMOR_SMOOTHNESS = 500
TUMOR_COLORS = [(1, 0, 0), (0, 1, 0), (0.5, 0.5, 0), (0, 0, 1)]  # RGB percentages
TUMOR_LABELS = [1, 2, 3, 4]
TUMOR_OPACITY = 1.0

# files to load into view
BRAIN_FILE = "./data/original/HGG/Brats17_2013_2_1/Brats17_2013_2_1_t1ce.nii.gz"
TUMOR_FILE = "./data/original/HGG/Brats17_2013_2_1/Brats17_2013_2_1_seg.nii.gz"


class NiiObject:
    def __init__(self):
        self.file = None
        self.reader = None
        self.labels = []


class NiiLabel:
    def __init__(self, color, opacity, smoothness):
        self.actor = None
        self.property = None
        self.smoother = None
        self.color = color
        self.opacity = opacity
        self.smoothness = smoothness


class ErrorObserver:
    def __init__(self):
        self.__ErrorOccurred = False
        self.__ErrorMessage = None
        self.CallDataType = 'string0'

    def __call__(self, obj, event, message):
        self.__ErrorOccurred = True
        self.__ErrorMessage = message

    def ErrorOccurred(self):
        occ = self.__ErrorOccurred
        self.__ErrorOccurred = False
        return occ

    def ErrorMessage(self):
        return self.__ErrorMessage


class MainWindow(QtWidgets.QMainWindow, QtWidgets.QApplication):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)

        # base setup
        self.renderer, self.frame, self.vtk_widget, self.interactor, self.render_window = self.setup()
        self.brain, self.tumor = setup_brain(self.renderer), setup_tumor(self.renderer)

        # setup brain projection
        self.brain_image_prop = setup_projection(self.brain, self.renderer)

        # detect any missing labels for the tumor
        # detect_missing_labels(self.tumor, self.render_window)

        # brain pickers
        self.brain_threshold_sp = self.create_new_picker(1000, 0, 5, BRAIN_THRESHOLD, self.brain_threshold_vc)
        self.brain_opacity_sp = self.create_new_picker(1.0, 0.0, 0.1, BRAIN_OPACITY, self.brain_opacity_vc)
        self.brain_smoothness_sp = self.create_new_picker(1000, 100, 100, BRAIN_SMOOTHNESS, self.brain_smoothness_vc)
        self.brain_projection_cb = self.add_brain_projection()

        # tumor pickers
        self.tumor_opacity_sp = self.create_new_picker(1.0, 0.0, 0.1, TUMOR_OPACITY, self.tumor_opacity_vc)
        self.tumor_smoothness_sp = self.create_new_picker(1000, 100, 100, TUMOR_SMOOTHNESS, self.tumor_smoothness_vc)
        self.tumor_label_cbs = []

        # create grid for all widgets
        self.grid = QtWidgets.QGridLayout()

        # add each widget
        self.add_vtk_window_widget()
        self.add_brain_settings_widget()
        self.add_tumor_settings_widget()
        self.add_views_widget()

        #  set layout and show
        self.render_window.Render()
        self.setWindowTitle(APPLICATION_TITLE)
        self.frame.setLayout(self.grid)
        self.setCentralWidget(self.frame)
        self.set_axial_view()
        self.interactor.Initialize()
        self.show()

    @staticmethod
    def setup():
        """
        Create and setup the base vtk and Qt objects for the application
        """
        renderer = vtk.vtkRenderer()
        frame = QtWidgets.QFrame()
        vtk_widget = QVTKRenderWindowInteractor()
        interactor = vtk_widget.GetRenderWindow().GetInteractor()
        render_window = vtk_widget.GetRenderWindow()

        frame.setAutoFillBackground(True)
        vtk_widget.GetRenderWindow().AddRenderer(renderer)
        render_window.AddRenderer(renderer)
        interactor.SetRenderWindow(render_window)
        interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        return renderer, frame, vtk_widget, interactor, render_window

    def add_vtk_window_widget(self):
        base_brain_file = os.path.basename(BRAIN_FILE)
        base_tumor_file = os.path.basename(TUMOR_FILE)
        object_title = str.format("Brain: {}          Tumor: {}", base_brain_file, base_tumor_file)
        object_group_box = QtWidgets.QGroupBox(object_title)
        object_layout = QtWidgets.QVBoxLayout()
        object_layout.addWidget(self.vtk_widget)
        object_group_box.setLayout(object_layout)
        self.grid.addWidget(object_group_box, 0, 2, 5, 5)

    def add_brain_settings_widget(self):
        brain_group_box = QtWidgets.QGroupBox("Brain Settings")
        brain_group_layout = QtWidgets.QGridLayout()
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Threshold"), 0, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Opacity"), 1, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Smoothness"), 2, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Projection"), 3, 0)
        brain_group_layout.addWidget(self.brain_threshold_sp, 0, 1)
        brain_group_layout.addWidget(self.brain_opacity_sp, 1, 1)
        brain_group_layout.addWidget(self.brain_smoothness_sp, 2, 1)
        brain_group_layout.addWidget(self.brain_projection_cb, 3, 1)
        brain_group_box.setLayout(brain_group_layout)
        self.grid.addWidget(brain_group_box, 0, 0, 1, 2)

    def add_tumor_settings_widget(self):
        tumor_settings_group_box = QtWidgets.QGroupBox("Tumor Settings")
        tumor_settings_layout = QtWidgets.QGridLayout()
        tumor_settings_layout.addWidget(QtWidgets.QLabel("Tumor Opacity"), 0, 0)
        tumor_settings_layout.addWidget(QtWidgets.QLabel("Tumor Smoothness"), 1, 0)
        tumor_settings_layout.addWidget(self.tumor_opacity_sp, 0, 1)
        tumor_settings_layout.addWidget(self.tumor_smoothness_sp, 1, 1)
        tumor_multi_color_radio = QtWidgets.QRadioButton("Multi Color")
        tumor_multi_color_radio.setChecked(True)
        tumor_multi_color_radio.clicked.connect(self.tumor_multi_color_radio_checked)
        tumor_single_color_radio = QtWidgets.QRadioButton("Single Color")
        tumor_single_color_radio.clicked.connect(self.tumor_single_color_radio_checked)
        tumor_settings_layout.addWidget(tumor_multi_color_radio, 2, 0)
        tumor_settings_layout.addWidget(tumor_single_color_radio, 2, 1)
        tumor_settings_layout.addWidget(self.create_new_separator(), 3, 0, 1, 2)
        self.tumor_label_cbs = [QtWidgets.QCheckBox("Label 1"),
                                QtWidgets.QCheckBox("Label 2"),
                                QtWidgets.QCheckBox("Label 3"),
                                QtWidgets.QCheckBox("Label 4")]
        tumor_settings_layout.addWidget(self.tumor_label_cbs[0], 4, 0)
        tumor_settings_layout.addWidget(self.tumor_label_cbs[1], 4, 1)
        tumor_settings_layout.addWidget(self.tumor_label_cbs[2], 5, 0)
        tumor_settings_layout.addWidget(self.tumor_label_cbs[3], 5, 1)
        tumor_settings_group_box.setLayout(tumor_settings_layout)
        self.grid.addWidget(tumor_settings_group_box, 1, 0, 2, 2)

        for i, cb in enumerate(self.tumor_label_cbs):
            if self.tumor.labels[i].actor:
                cb.setChecked(True)
                cb.clicked.connect(self.tumor_label_checked)
            else:
                cb.setDisabled(True)

    def add_views_widget(self):
        axial_view = QtWidgets.QPushButton("Axial")
        coronal_view = QtWidgets.QPushButton("Coronal")
        sagittal_view = QtWidgets.QPushButton("Sagittal")
        views_box = QtWidgets.QGroupBox("Views")
        views_box_layout = QtWidgets.QVBoxLayout()
        views_box_layout.addWidget(axial_view)
        views_box_layout.addWidget(coronal_view)
        views_box_layout.addWidget(sagittal_view)
        views_box.setLayout(views_box_layout)
        self.grid.addWidget(views_box, 3, 0, 2, 2)
        axial_view.clicked.connect(self.set_axial_view)
        coronal_view.clicked.connect(self.set_coronal_view)
        sagittal_view.clicked.connect(self.set_sagittal_view)

    @staticmethod
    def create_new_picker(max_value, min_value, step, picker_value, value_changed_func):
        if isinstance(max_value, int):
            picker = QtWidgets.QSpinBox()
        else:
            picker = QtWidgets.QDoubleSpinBox()

        picker.setMaximum(max_value)
        picker.setMinimum(min_value)
        picker.setSingleStep(step)
        picker.setValue(picker_value)
        picker.valueChanged.connect(value_changed_func)
        return picker

    def add_brain_projection(self):
        projection_cb = QtWidgets.QCheckBox("")
        projection_cb.clicked.connect(self.brain_projection_vc)
        return projection_cb

    def tumor_label_checked(self):
        for i, cb in enumerate(self.tumor_label_cbs):
            if cb.isChecked():
                self.tumor.labels[i].property.SetOpacity(self.tumor_opacity_sp.value())
            elif cb.isEnabled():  # labels without data are disabled
                self.tumor.labels[i].property.SetOpacity(0)
        self.render_window.Render()

    def tumor_single_color_radio_checked(self):
        for label in self.tumor.labels:
            if label.property:
                label.property.SetColor(TUMOR_COLORS[0])
        self.render_window.Render()

    def tumor_multi_color_radio_checked(self):
        for label in self.tumor.labels:
            if label.property:
                label.property.SetColor(label.color)
        self.render_window.Render()

    def brain_projection_vc(self):
        checked = self.brain_projection_cb.isChecked()
        self.brain_image_prop.SetOpacity(checked)
        self.brain_projection_cb.repaint()
        self.render_window.Render()

    def brain_opacity_vc(self):
        opacity = round(self.brain_opacity_sp.value(), 2)
        self.brain.labels[0].property.SetOpacity(opacity)
        self.render_window.Render()

    def brain_threshold_vc(self):
        self.process_changes()
        threshold = self.brain_threshold_sp.value()
        self.brain.labels[0].extractor.SetValue(0, threshold)
        self.render_window.Render()

    def brain_smoothness_vc(self):
        self.process_changes()
        smoothness = self.brain_smoothness_sp.value()
        self.brain.labels[0].smoother.SetNumberOfIterations(smoothness)
        self.render_window.Render()

    def tumor_opacity_vc(self):
        opacity = round(self.tumor_opacity_sp.value(), 2)
        for label in self.tumor.labels:
            if label.property:
                label.property.SetOpacity(opacity)
        self.render_window.Render()

    def tumor_smoothness_vc(self):
        self.process_changes()
        smoothness = self.tumor_smoothness_sp.value()
        for label in self.tumor.labels:
            if label.smoother:
                label.smoother.SetNumberOfIterations(smoothness)
        self.render_window.Render()

    def set_axial_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[0], fp[1], fp[2] + dist)
        self.renderer.GetActiveCamera().SetViewUp(0.0, 1.0, 0.0)
        self.renderer.GetActiveCamera().Zoom(1.8)
        self.render_window.Render()

    def set_coronal_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[0], fp[2] + dist, fp[1])
        self.renderer.GetActiveCamera().SetViewUp(0.0, 0.5, 0.5)
        self.renderer.GetActiveCamera().Zoom(1.8)
        self.render_window.Render()

    def set_sagittal_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[2] + dist, fp[1], fp[0])
        self.renderer.GetActiveCamera().SetViewUp(0.0, 0.5, 0.5)
        self.renderer.GetActiveCamera().Zoom(1.8)
        self.render_window.Render()

    @staticmethod
    def create_new_separator():
        horizontal_line = QtWidgets.QWidget()
        horizontal_line.setFixedHeight(1)
        horizontal_line.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        horizontal_line.setStyleSheet("background-color: #c8c8c8;")
        return horizontal_line

    @staticmethod
    def process_changes():
        for _ in range(10):
            app.processEvents()
            time.sleep(0.1)


def read_volume(file_name):
    reader = vtk.vtkNIFTIImageReader()
    reader.SetFileNameSliceOffset(1)
    reader.SetDataByteOrderToBigEndian()
    reader.SetFileName(file_name)
    reader.Update()
    return reader


def create_brain_extractor(brain):
    brain_extractor = vtk.vtkFlyingEdges3D()
    brain_extractor.SetInputConnection(brain.reader.GetOutputPort())
    brain_extractor.SetValue(0, BRAIN_THRESHOLD)
    return brain_extractor


def create_tumor_extractor(tumor):
    tumor_extractor = vtk.vtkDiscreteMarchingCubes()
    tumor_extractor.SetInputConnection(tumor.reader.GetOutputPort())
    return tumor_extractor


def create_polygon_reducer(extractor):
    reducer = vtk.vtkDecimatePro()
    reducer.AddObserver('ErrorEvent', error_observer)  # used to detect labels that don't exist
    reducer.SetInputConnection(extractor.GetOutputPort())
    reducer.SetTargetReduction(0.5)
    reducer.PreserveTopologyOn()

    return reducer


def create_smoother(reducer, smoothness):
    smoother = vtk.vtkSmoothPolyDataFilter()
    smoother.SetInputConnection(reducer.GetOutputPort())
    smoother.SetNumberOfIterations(smoothness)
    return smoother


def create_normals(smoother):
    brain_normals = vtk.vtkPolyDataNormals()
    brain_normals.SetInputConnection(smoother.GetOutputPort())
    brain_normals.SetFeatureAngle(60.0)  # controls the smoothness of the edges
    return brain_normals


def create_stripper(normals):
    brain_stripper = vtk.vtkStripper()
    brain_stripper.SetInputConnection(normals.GetOutputPort())
    return brain_stripper


def create_mapper(stripper):
    brain_mapper = vtk.vtkPolyDataMapper()
    brain_mapper.SetInputConnection(stripper.GetOutputPort())
    brain_mapper.ScalarVisibilityOff()
    brain_mapper.Update()
    return brain_mapper


def create_property(opacity, color):
    prop = vtk.vtkProperty()
    prop.SetColor(color[0], color[1], color[2])
    prop.SetOpacity(opacity)
    return prop


def create_actor(mapper, prop):
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.SetProperty(prop)
    return actor


def create_tumor_table():
    m_mask_opacity = 1
    brain_lut = vtk.vtkLookupTable()
    brain_lut.SetRange(0, 4)
    brain_lut.SetRampToLinear()
    brain_lut.SetValueRange(0, 1)
    brain_lut.SetHueRange(0, 0)
    brain_lut.SetSaturationRange(0, 0)

    brain_lut.SetNumberOfTableValues(10)
    brain_lut.SetTableRange(0, 9)
    brain_lut.SetTableValue(0, 0, 0, 0, 0)
    brain_lut.SetTableValue(1, 1, 0, 0, m_mask_opacity)  # RED
    brain_lut.SetTableValue(2, 0, 1, 0, m_mask_opacity)  # GREEN
    brain_lut.SetTableValue(3, 1, 1, 0, m_mask_opacity)  # YELLOW
    brain_lut.SetTableValue(4, 0, 0, 1, m_mask_opacity)  # BLUE
    brain_lut.SetTableValue(5, 1, 0, 1, m_mask_opacity)  # MAGENTA
    brain_lut.SetTableValue(6, 0, 1, 1, m_mask_opacity)  # CYAN
    brain_lut.SetTableValue(7, 1, 0.5, 0.5, m_mask_opacity)  # RED_2
    brain_lut.SetTableValue(8, 0.5, 1, 0.5, m_mask_opacity)  # GREEN_2
    brain_lut.SetTableValue(9, 0.5, 0.5, 1, m_mask_opacity)  # BLUE_2
    brain_lut.Build()
    return brain_lut


def create_table():
    table = vtk.vtkLookupTable()
    table.SetRange(0.0, 1675.0)  # +1
    table.SetRampToLinear()
    table.SetValueRange(0, 1)
    table.SetHueRange(0, 0)
    table.SetSaturationRange(0, 0)


def add_surface_rendering(nii_object, label_idx, label_value):
    nii_object.labels[label_idx].extractor.SetValue(0, label_value)
    nii_object.labels[label_idx].extractor.Update()

    # if the cell size is 0 then there is no label_idx data
    if nii_object.labels[label_idx].extractor.GetOutput().GetMaxCellSize():
        reducer = create_polygon_reducer(nii_object.labels[label_idx].extractor)
        smoother = create_smoother(reducer, nii_object.labels[label_idx].smoothness)
        normals = create_normals(smoother)
        stripper = create_stripper(normals)
        actor_mapper = create_mapper(stripper)
        actor_property = create_property(nii_object.labels[label_idx].opacity, nii_object.labels[label_idx].color)
        actor = create_actor(actor_mapper, actor_property)
        nii_object.labels[label_idx].actor = actor
        nii_object.labels[label_idx].smoother = smoother
        nii_object.labels[label_idx].property = actor_property


def setup_projection(brain, renderer):
    slice_mapper = vtk.vtkImageResliceMapper()
    slice_mapper.SetInputConnection(brain.reader.GetOutputPort())
    slice_mapper.SliceFacesCameraOn()
    slice_mapper.SliceAtFocalPointOn()
    slice_mapper.BorderOff()
    brain_image_prop = vtk.vtkImageProperty()
    brain_image_prop.SetColorWindow(500)
    brain_image_prop.SetColorLevel(500)
    brain_image_prop.SetAmbient(1.0)
    brain_image_prop.SetDiffuse(1.0)
    brain_image_prop.SetOpacity(0.0)
    brain_image_prop.SetInterpolationTypeToLinear()
    image_slice = vtk.vtkImageSlice()
    image_slice.SetMapper(slice_mapper)
    image_slice.SetProperty(brain_image_prop)
    renderer.AddViewProp(image_slice)
    return brain_image_prop


def setup_brain(renderer):
    brain = NiiObject()
    brain.file = BRAIN_FILE
    brain.reader = read_volume(brain.file)
    brain.labels.append(NiiLabel(BRAIN_COLORS[0], BRAIN_OPACITY, BRAIN_SMOOTHNESS))
    brain.labels[0].extractor = create_brain_extractor(brain)
    add_surface_rendering(brain, 0, 20)
    renderer.AddActor(brain.labels[0].actor)
    return brain


def setup_tumor(renderer):
    tumor = NiiObject()
    tumor.file = TUMOR_FILE
    tumor.reader = read_volume(tumor.file)
    n_labels = int(tumor.reader.GetOutput().GetScalarRange()[1])
    for label_idx in range(0, n_labels):
        tumor.labels.append(NiiLabel(TUMOR_COLORS[label_idx], TUMOR_OPACITY, TUMOR_SMOOTHNESS))
        tumor.labels[label_idx].extractor = create_tumor_extractor(tumor)
        add_surface_rendering(tumor, label_idx, label_idx + 1)
        renderer.AddActor(tumor.labels[label_idx].actor)

    return tumor


def redirect_vtk_messages():
    """ Redirect VTK related error messages to a file."""
    import tempfile
    tempfile.template = 'vtk-err'
    f = tempfile.mktemp('.log')
    log = vtk.vtkFileOutputWindow()
    log.SetFlush(1)
    log.SetFileName(f)
    log.SetInstance(log)


if __name__ == "__main__":
    error_observer = ErrorObserver()
    # redirect_vtk_messages()
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec_())
