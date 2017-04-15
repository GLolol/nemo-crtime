#!/usr/bin/env python
import subprocess
import struct
import os
import time

import traceback
import locale
import gettext
import gi
gi.require_version('Nemo', '3.0')
from gi.repository import Nemo, GObject, Gio

# Constants that should be kept in sync with Nemo...
NEMO_DATE_FORMAT_LOCALE = 0
NEMO_DATE_FORMAT_ISO = 1
NEMO_DATE_FORMAT_INFORMAL = 2

def get_file_system(path):
    """
    Returns the file system the given file is on.
    """
    assert isinstance(path, basestring), "Bad object type given for path"
    df = subprocess.check_output(['df', '-T', path])
    df = df.decode('utf-8').splitlines()[-1]
    return df.split()[1]

def get_vfat_crtime(path):
    """
    Returns the VFAT (FAT32) file creation time for the given path as a Unix timestamp.
    """
    # The vfat driver actually exposes the creation time as the ctime value
    # (creation time on Unix).
    ctime = os.stat(path).st_ctime
    return ctime

def get_ntfs_crtime(path):
    """
    Returns the NTFS file creation time for the given path as a Unix timestamp.
    """
    raw_crtime = subprocess.check_output(['getfattr', '--only-values', '-n', 'system.ntfs_crtime_be', path])
    # From http://www.tuxera.com/community/ntfs-3g-advanced/extended-attributes/
    # NTFS times are stored as time stamps "representing the number of 100-nanosecond
    # intervals since January 1, 1601 (UTC)". Here, we convert it into Unix time
    int_time = struct.unpack('>Q', raw_crtime)[0]/10000000 - 11644473600
    return int_time

def get_crtime(path):
    """
    Returns the file creation time for the given path.
    """
    fs = get_file_system(path)
    if fs == 'fuseblk':
        crtime = get_ntfs_crtime(path)
    elif fs == 'vfat':
        crtime = get_vfat_crtime(path)
    else:
        return
    return crtime

# Set up i18n.
TEXTDOMAIN = "nemo-crtime"
locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain(TEXTDOMAIN)
gettext.textdomain(TEXTDOMAIN)
_ = gettext.gettext

class NemoCreationTime(GObject.GObject, Nemo.ColumnProvider, Nemo.InfoProvider,
                       Nemo.NameAndDescProvider):

    def get_name_and_desc(self):
        """Return the plugin info for the plugin manager."""
        return [_("Nemo-Crtime:::Display creation time for files/folders on NTFS / FAT32 file systems.")]

    def get_columns(self):
        """Return the list of columns provided by this extension."""
        return (Nemo.Column(name="NemoCrtime::creation_time_column",
                            attribute="creation_time",
                            # For consistency with Nemo's style (Date Modified, Date Accessed, ...)
                            label=_("Date Created"),
                            description=_("File/folder creation time (NTFS/FAT32)")),)


    def update_file_info(self, fileinfo):
        """Updates the Nemo file attributes for the given file.."""

        if fileinfo.get_uri_scheme() == 'file':
            filename = fileinfo.get_location().get_path()
            try:
                crtime = get_crtime(filename)
            except:
                traceback.print_exc()  # Log exceptions
            else:
                # get_crtime() returns None if on an unsupported file system
                if crtime is not None:
                    struct_time = time.gmtime(crtime)
                    # Respect Nemo's time formatting. XXX: can we get this data from Nemo directly?
                    settings = Gio.Settings.new('org.nemo.preferences')
                    timeformat = settings.get_enum('date-format')

                    if timeformat == NEMO_DATE_FORMAT_LOCALE:
                        formatted_time = time.strftime('%c', struct_time)
                    else:  # XXX: no support for "informal" time format yet
                        formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', struct_time)
                    fileinfo.add_string_attribute('creation_time', formatted_time)

        return Nemo.OperationResult.COMPLETE


if __name__ == '__main__':
    import time
    import sys

    try:
        path = sys.argv[1]
    except IndexError:
        print(_("ERROR: need one command line argument: filename"))
        sys.exit(1)

    crtime = get_crtime(path)
    if not crtime:
        raise RuntimeError(_("Unsupported filesystem"))
    print(time.ctime(crtime))
