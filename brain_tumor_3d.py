import sys
import argparse
from MainWindow import *
import config


def redirect_vtk_messages():
    """ Redirect VTK related error messages to a file."""
    import tempfile
    tempfile.template = 'vtk-err'
    f = tempfile.mktemp('.log')
    log = vtk.vtkFileOutputWindow()
    log.SetFlush(1)
    log.SetFileName(f)
    log.SetInstance(log)


def file_choices(file):
    ext = os.path.basename(file).split(os.extsep, 1)
    if ext[1] != 'nii.gz':
        parser.error("File doesn't end with 'nii.gz'. Found: {}".format(ext[1]))
    return file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Reads Nii.gz Files and renders them in 3D.')
    parser.add_argument('-i', type=lambda fn: file_choices(fn), help='an mri scan (nii.gz)')
    parser.add_argument('-m', type=lambda fn: file_choices(fn), help='the segmentation mask (nii.gz)')
    args = parser.parse_args()

    redirect_vtk_messages()
    app = QtWidgets.QApplication(sys.argv)
    app.BRAIN_FILE = args.i
    app.TUMOR_FILE = args.m
    window = MainWindow(app)
    sys.exit(app.exec_())
