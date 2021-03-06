import configparser
from inspect import getsourcefile
from json import load
import os
import re
import sqlite3
import webbrowser

import pyzo
from pyzo import translate
from pyzo.util.qt import QtCore, QtGui, QtWidgets
from .utils import splitName, splitNameCleaner, joinName


# Constants
WORKSPACE_INIT = os.path.abspath(getsourcefile(lambda: 0))
WORKSPACE_DIR = os.path.dirname(WORKSPACE_INIT)
CONF_FILE = os.path.join(WORKSPACE_DIR, "config.ini")
UNODOC_DB = os.path.join(WORKSPACE_DIR, "unoDoc.db")

# Read configuration
config = configparser.ConfigParser()
config.read(CONF_FILE)

FORUM_PATH = config.get("GENERAL", "forum_path")
FORUM_SUFIX = config.get("GENERAL", "forum_sufix")
SNIPPET_PATH = config.get("GENERAL", "snippet_path")
SNIPPET_SUFIX = config.get("GENERAL", "snippet_sufix")

# print("**********************")
# print("WORKSPACE_INIT = " + WORKSPACE_INIT)
# print("WORKSPACE_DIR = " + WORKSPACE_DIR)
# print("CONF_FILE = " + CONF_FILE)
# print("UNODOC_DB = " + UNODOC_DB)

# print("FORUM_PATH = " + FORUM_PATH)
# print("FORUM_SUFIX = " + FORUM_SUFIX)
# print("SNIPPET_PATH = " + SNIPPET_PATH)
# print("SNIPPET_SUFIX = " + SNIPPET_SUFIX)

# connect documentation database
conn = sqlite3.connect(UNODOC_DB)

# JSON serialization path
RESULTFILE_JSON = "result.txt"
RESULT_JSON = os.path.join(WORKSPACE_DIR, RESULTFILE_JSON)
# Pickle path
RESULTFILE_PICKLE = "result.pkl"
RESULT_PICKLE = os.path.join(WORKSPACE_DIR, RESULTFILE_PICKLE)
# History file
HISTORYFILE = "ws_history.txt"
HISTORY = os.path.join(WORKSPACE_DIR, HISTORYFILE)
DIALOG_INPUT = []


# Result file
def createResultFile():

    if os.path.exists(RESULT_JSON):
        os.remove(RESULT_JSON)

    with open(RESULT_JSON, "w") as f:
        f.write('{}')


def getResultFilePath():
    return  RESULT_JSON


# History file
def createHistoryFile():

    if os.path.exists(HISTORY):
        os.remove(HISTORY)

    with open(HISTORY, "w") as f:
        f.write("\n")


def getHistoryFilePath():
    return HISTORY


def writeHistory(itemlist):
    """ Write history in the file"""
    with open(HISTORY, "w") as hist:
        for item in itemlist:
            hist.write("{}\n".format(item))


def readHistory():
    """Read history from file"""
    with open(HISTORY, "r") as f:
        lines = f.readlines()

    l = [line.rstrip("\n") for line in lines]
    return l


def formatReference(signature, description, bold=[]):

    # format signature
    signature = signature.replace("&newline&", "\n")
    # bold
    if bold:
        for m in bold:
            signature = re.sub(
                r"\b" + m + r"\b", "<strong>{}</strong>".format(m), signature
            )
    # bold red
    for r in ["set raises", "get raises", "raises"]:
        signature = signature.replace(
            r, '<span style="font-weight:bold;color:red">{}</span>'.format(r)
        )

    # format description
    description = description.replace("&newline&&newline&", "<p></p>")
    description = description.replace("&newline&", "<p></p>")
    # bold
    for d in ["Parameters", "Exceptions", "Returns", "Enumerator"]:
        description = re.sub(
            r"\b{}\b".format(d),
            "<p style='font-weight:bold'>{}</p>".format(d),
            description,
        )
    # bold blue
    for d in ["See also", "See Also", "Reference"]:
        description = re.sub(
            r"\b{}\b".format(d),
            "<p style='font-weight:bold;color:blue'>{}</p>".format(d),
            description,
        )

    # bold red
    for w in ["Deprecated", "Attention"]:
        description = re.sub(
            r"\b{}\b".format(w),
            '<span style="font-weight:bold;color:red">{}</span>'.format(w),
            description,
        )

    return signature, description


class PyUNOWorkspaceItem(QtWidgets.QTreeWidgetItem):
    def __lt__(self, otherItem):
        column = self.treeWidget().sortColumn()
        try:
            return float(self.text(column).strip("[]")) > float(
                otherItem.text(column).strip("[]")
            )
        except ValueError:
            return self.text(column) > otherItem.text(column)


class PyUNOWorkspaceProxy(QtCore.QObject):
    """ WorkspaceProxy

    A proxy class to handle the asynchonous behaviour of getting information
    from the shell. The workspace tool asks for a certain name, and this
    class notifies when new data is available using a qt signal.

    """

    haveNewData = QtCore.Signal()

    def __init__(self):
        QtCore.QObject.__init__(self)

        # Variables
        self._variables = []
        self._uno_dict = {}

        # Element to get more info of
        self._name = ""

        # Bind to events
        # self._variables = []

        # Element to get more info of
        self._name = ""

        # Bind to events
        pyzo.shells.currentShellChanged.connect(self.onCurrentShellChanged)
        pyzo.shells.currentShellStateChanged.connect(
            self.onCurrentShellStateChanged
        )

        # Initialize
        self.onCurrentShellStateChanged()

    def addNamePart(self, part):
        """ addNamePart(part)
        Add a part to the name.
        """
        parts = splitName(self._name)
        parts.append(part)
        self.setName(joinName(parts))

    def setName(self, name):
        """ setName(name)
        Set the name that we want to know more of.
        """

        self._name = name
        shell = pyzo.shells.getCurrentShell()
        if shell:
            # via unoinspect
            if not self._name or self._name.endswith(".value"):
                createResultFile()
            else:
                shell.executeCommand(
                     "Inspector().inspect(" + str(self._name) + ")\n")
            # via pyzo
            future = shell._request.dir2(self._name)
            future.add_done_callback(self.processResponse)

            if pyzo.config.tools.pyzopyunoworkspace.clearScreenAfter:
                shell.clearScreen()

    def goUp(self):
        """ goUp()
        Cut the last part off the name.
        """
        if self._name:
            parts = splitNameCleaner(self._name)
            if parts:
                parts.pop()

            self.setName(joinName(parts))

    def onCurrentShellChanged(self):
        """ onCurrentShellChanged()
        When no shell is selected now, update this. In all other cases,
        the onCurrentShellStateChange will be fired too.
        """
        shell = pyzo.shells.getCurrentShell()
        if not shell:
            self._variables = []
            self._uno_dict = {}
            self.haveNewData.emit()

    def onCurrentShellStateChanged(self):
        """ onCurrentShellStateChanged()
        Do a request for information!
        """
        shell = pyzo.shells.getCurrentShell()
        if not shell:
            # Should never happen I think, but just to be sure
            self._variables = []
            self._uno_dict = {}

        elif shell._state.lower() != "busy":
            # via pyzo
            future = shell._request.dir2(self._name)
            future.add_done_callback(self.processResponse)

    def processResponse(self, future):
        """ processResponse(response)
        We got a response, update our list and notify the tree.
        """

        response = []

        # Process future
        if future.cancelled():
            pass  # print('Introspect cancelled') # No living kernel
        elif future.exception():
            print("Introspect-queryDoc-exception: ", future.exception())
        else:
            response = future.result()

        # Introspection via pyzo
        self._variables = response

        # Introspection via unoinspect - read json
        with open(RESULT_JSON) as resultf:
            self._uno_dict = load(resultf)
        self.haveNewData.emit()


class PyUNOWorkspaceTree(QtWidgets.QTreeWidget):
    """ WorkspaceTree

    The tree that displays the items in the current namespace.
    I first thought about implementing this using the mode/view
    framework, but it is so much work and I can't seem to fully
    understand how it works :(

    The QTreeWidget is so very simple and enables sorting very
    easily, so I'll stick with that ...

    """

    def __init__(self, parent):
        QtWidgets.QTreeWidget.__init__(self, parent)

        # create JSON serialization file
        if not os.path.isfile(RESULT_JSON) or not os.path.isfile(RESULT_PICKLE):
            createResultFile()

        # create history file
        if not os.path.isfile(HISTORY):
            createHistoryFile()

        self._config = parent._config
        self.old_item = ""
        self._name_item = ""

        # tree selected item
        self._tree_name = ""
        self._tree_type = ""
        self._tree_repr = ""

        # Set header stuff
        self.setHeaderHidden(False)
        self.setColumnCount(3)
        self.setHeaderLabels(["Name", "Type", "Repr"])
        # Set first column width
        self.setColumnWidth(0, 170)
        self.setSortingEnabled(True)

        # Nice rows
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(False)

        # Create proxy
        self._proxy = PyUNOWorkspaceProxy()
        self._proxy.haveNewData.connect(self.fillWorkspace)

        # For menu
        self.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        self._menu = QtWidgets.QMenu()
        self._menu.triggered.connect(self.contextMenuTriggered)

        # Bind to events
        self.itemActivated.connect(self.onItemExpand)
        self.clicked.connect(self.onItemClicked)

    def contextMenuEvent(self, event):
        """ contextMenuEvent(event)
        Show the context menu.
        """

        QtWidgets.QTreeView.contextMenuEvent(self, event)

        # Get if an item is selected
        item = self.currentItem()
        if not item:
            return

        # Create menu
        self._menu.clear()

        # menu items
        workspace_menu = [
            # "Show namespace",
            # "Delete",
            "Copy",
            "sep",
            "Open Office Forum Search",
            "Open Office Snippets Search",
        ]

        for a in workspace_menu:
            if a == "sep":
                self._menu.addSeparator()
            else:
                action = self._menu.addAction(a)
                parts = splitName(self._proxy._name)
                parts.append(item.text(0))
                action._objectName = joinName(parts)
                action._item = item

        # Show
        self._menu.popup(QtGui.QCursor.pos() + QtCore.QPoint(3, 3))

    def contextMenuTriggered(self, action):
        """ contextMenuTriggered(action)
        Process a request from the context menu.
        """

        # Get text
        req = action.text()
        # Get current shell
        shell = pyzo.shells.getCurrentShell()

        search = splitName(action._objectName)
        ob = ".".join(search[:-1])
        search = search[-1]

        if "Copy" in req:
            sys_clip = QtWidgets.QApplication.clipboard()
            sys_clip.setText(search)

        # ------- PyUNO ----------------

        elif "Open Office Forum Search" in req:
            # Search in forum
            url = FORUM_PATH + search + FORUM_SUFIX
            webbrowser.open(url)

        elif "Open Office Snippets Search" in req:
            # Search in forum snippets
            url = SNIPPET_PATH + search + SNIPPET_SUFIX
            webbrowser.open(url)

        # ------- End PyUNO ----------------

        elif "Delete" in req:
            # Delete the variable
            if shell:
                shell.processLine("del " + action._objectName)

    def onItemExpand(self, item):
        """ onItemExpand(item)
        Inspect the attributes of that item
        Add arguments to item if needed and then inspect the attributes of that item.
        """
        inspect_item = item.text(0)

        # if item is UNO method
        if item.text(0)[0].islower():
            # get item name and arguments
            name = item.text(0)
            typ = item.text(1)
            rep = item.text(2)

            if name == "value" and (typ == "pyuno.struct" or typ == "struct"):
                pass
            elif rep == "( )":
                inspect_item = inspect_item + "()"
            elif rep.startswith("(") and len(rep) > 3:
                # show dialog to add arguments
                dialog = InputDialog(self)
                dialog.setWindowTitle(
                    translate("menu dialog", "Add arguments to: ") + name
                )
                rep = rep.replace(",", ",\n ")
                dialog._argument_info.setText(rep)

                dialog_result = dialog.exec_()
                if dialog_result == QtWidgets.QDialog.Accepted:
                    if dialog._argument.text() == "":
                        inspect_item = ""
                    else:
                        inspect_item = (
                            inspect_item + "(" + dialog._argument.text() + ")"
                        )
                else:
                    inspect_item = ""

        if inspect_item:
            # set item for inspection
            self._proxy.addNamePart(inspect_item)

    def resetWidget(self):
        """ resetWidget
        Reset widgets to default.
        """
        self.parent()._element_names.clear()
        self.parent()._element_index.clear()
        self.parent()._enumerate_index.clear()
        self.parent()._description.setText(self.parent().initText)

        self.parent()._selection.setEnabled(False)
        self.parent()._element_names.setEnabled(False)
        self.parent()._element_index.setEnabled(False)
        self.parent()._enumerate_index.setEnabled(False)

    def fillWidget(self):
        """ fillWidget
        Fill/activate widgets.
        """

        if "getByName" in self._proxy._uno_dict.keys():
            if self._proxy._uno_dict["getByName"]["items"]:
                self.parent()._element_names.addItem("--Name--")
                self.parent()._element_names.addItems(
                    self._proxy._uno_dict["getByName"]["items"]
                )
                self.parent()._element_names.setEnabled(True)

        if "getByIndex" in self._proxy._uno_dict.keys():
            if self._proxy._uno_dict["getByIndex"]["items"]:
                self.parent()._element_index.addItem("--Index--")
                self.parent()._element_index.addItems(
                    self._proxy._uno_dict["getByIndex"]["items"]
                )
                self.parent()._element_index.setEnabled(True)

        if "createEnumeration" in self._proxy._uno_dict.keys():
            if self._proxy._uno_dict["createEnumeration"]["items"]:
                self.parent()._enumerate_index.addItem("--Enumeration--")
                self.parent()._enumerate_index.addItem("All")
                self.parent()._enumerate_index.addItems(
                    self._proxy._uno_dict["createEnumeration"]["items"]
                )
                self.parent()._enumerate_index.setEnabled(True)

        if "getCurrentSelection" in self._proxy._uno_dict.keys():
            if self._proxy._uno_dict["getCurrentSelection"]:
                self.parent()._selection.setEnabled(True)

    def fillWorkspace(self):
        """ fillWorkspace()
        Update the workspace tree.
        """

        # Clear tree and widget first
        self.clear()
        self.resetWidget()

        # Set name
        line = self.parent()._line
        line.setText(self._proxy._name)

        # Fill history and widgets
        if line.text():
            self.parent().onAddToHistory(line.text().strip())
        self.fillWidget()

        # Add elements
        for des in self._proxy._variables:

            # Get parts
            try:
                parts = des.split(",", 4)
            except:
                parts = list(des)

            if len(parts) < 4:
                continue
            # -- Name --
            name = parts[0]
            # -- Type, Repr --
            if name in self._proxy._uno_dict.keys():
                typ = str(self._proxy._uno_dict[name]["type"])
                rep = str(self._proxy._uno_dict[name]["repr"])
            else:
                typ = parts[1]
                rep = parts[-1]

            # Pop the 'kind' element
            kind = parts.pop(2)

            if kind in self._config.hideTypes:
                continue
            if name.startswith("_") and "private" in self._config.hideTypes:
                continue
            if name == "ImplementationName":
                pyzo.main.statusBar().showMessage(rep, 5000)
            if rep.startswith("pyuno object ("):
                rep = "pyuno object"

            # Create item
            item = PyUNOWorkspaceItem([name, typ, rep], 0)
            # item = PyUNOWorkspaceItem(parts, 0)
            self.addTopLevelItem(item)

            # Set background color
            # item.setBackground(0, QtGui.QColor(255, 255, 255))
            # item.setBackground(1, QtGui.QColor(255, 255, 255))
            # item.setBackground(2, QtGui.QColor(255, 255, 255))

            # Set tooltip
            # tt = "%s: %s" % (parts[0], parts[-1])
            # item.setToolTip(0, tt)
            # item.setToolTip(1, tt)
            # item.setToolTip(2, tt)

        # scroll on the start
        self.scrollToItem(self.topLevelItem(0))

        self.parent().displayEmptyWorkspace(
            self.topLevelItemCount() == 0 and self._proxy._name == ""
        )

    def onItemClicked(self):
        """ onItemClicked()
        If item clicked in the workspace tree show help
        """
        # Clear
        self.parent()._description.clear()
        self._tree_name = ""
        self._tree_type = ""
        self._tree_repr = ""

        # Get tree items
        items = self.currentItem()

        # store tree items in vars
        self._tree_name = str(items.data(0, 0))
        self._tree_type = str(items.data(1, 0))
        self._tree_repr = str(items.data(2, 0))

        # Find documentation for this item
        find = str(items.data(0, 0))

        try:
            kind = str(self._proxy._uno_dict[find]["desc"])
            # find in UNO or Python documentation
            if kind.startswith("uno"):
                # UNO
                self.unoDescriptions(find)
            else:
                # Python
                find = self.parent()._line.text() + "." + find
                self.queryDoc(find)
        except:
            t = "No information is available for: {}".format(find)
            self.parent()._description.setText(t)

    def queryDoc(self, name):
        """ Query the Python documentation for the text in the line edit. """
        # Get shell and ask for the documentation
        self._name_item = ""
        shell = pyzo.shells.getCurrentShell()
        if shell and name:
            future = shell._request.doc(name)
            future.add_done_callback(self.queryDoc_response)
            self._name_item = name

    def queryDoc_response(self, future):
        """ Process the response, python documentation, from the shell. """

        # Process future
        if future.cancelled():
            # print('Introspect cancelled') # No living kernel
            return
        elif future.exception():
            print("Introspect-queryDoc-exception: ", future.exception())
            return
        else:
            response = future.result()
            if not response:
                t = "No information is available for: {}".format(find)
                self.parent()._description.setText(t)
                return
            else:
                response_txt = str(response).split("\n")
                name = self._name_item.split(".")

                n = 0
                txt = ""
                start = (
                    self._name_item + "(",
                    name[-1],
                    "bool(",
                    "bytes(",
                    "dict(",
                    "int(",
                    "list(",
                    "str(",
                    "tuple(",
                )
                for i, des in enumerate(response_txt):
                    if i == 0:
                        if name[-1] in des:
                            des = des.replace(
                                name[-1],
                                '<span style="font-weight:bold;">{}</span>'.format(
                                    name[-1]
                                ),
                            )

                        res = "<p style = 'background-color: palegreen'>{}</p>".format(
                            des
                        )
                    elif des.startswith(start):
                        res = "<strong>{}</strong>".format(des)
                    else:
                        res = des + "\n"

                    res = "<p>{}</p>".format(res)

                    txt = txt + res

                    n += 1

                self.parent()._description.setText(txt)

    def unoDescriptions(self, find):
        """ Process UNO documentation. """

        if find.startswith("get"):
            getfind = find.replace("get", "")
        else:
            getfind = "get" + find

        cur = conn.cursor()
        cur.execute(
            "SELECT signature, description, reference FROM UNOtable WHERE name=? OR name =?",
            (find, getfind),
        )
        rows = cur.fetchall()
        if rows:
            self.parent()._desc_all_items.setText(str(len(rows)))
            self.parent()._desc_counter.setText("0")

            # set font size
            font = self.parent()._description.font()
            font.setPointSize(self._config.fontSizeHelp)
            self.parent()._description.setFont(QtGui.QFont(font))

            try:
                n = 0
                ok_counter = 0
                good = ""
                bad = ""
                for sig, desc, ref in rows:
                    desc = desc + "&newline&Reference &newline&" + ref
                    sig, desc = formatReference(sig, desc, bold=[find, getfind])

                    # signature color
                    sig_OK = False
                    if len(rows) == 1:
                        # if only one result, color green
                        sig = "<p style = 'background-color: palegreen'>{}</p>".format(
                            sig
                        )
                        ok_counter += 1
                        sig_OK = True

                    elif self._tree_repr in sig:
                        # if param is OK, color green
                        sig = "<p style = 'background-color: palegreen'>{}</p>".format(
                            sig
                        )
                        ok_counter += 1
                        sig_OK = True

                    elif self._tree_repr == "pyuno object" and sig.startswith(
                        "com.sun.star" + self._tree_type
                    ):
                        # if param is OK, color green
                        sig = "<p style = 'background-color: palegreen'>{}</p>".format(
                            sig
                        )
                        ok_counter += 1
                        sig_OK = True

                    else:
                        sig = "<p style = 'background-color: lightgray'>{}</p>".format(
                            sig
                        )
                        sig_OK = False

                    desc = "<p>{}</p>".format(desc)

                    if sig_OK:
                        good = good + sig + desc
                    else:
                        bad = bad + sig + desc

                    sig = ""
                    desc = ""
                    # set font size
                    font = self.parent()._description.font()
                    font.setPointSize(self._config.fontSizeHelp)
                    self.parent()._description.setFont(QtGui.QFont(font))

                    n += 1

                # show description
                txt = good + bad

                self.parent()._description.setText(txt)
                self.parent()._desc_counter.setText(str(ok_counter))
            except Exception as err:
                print(err)

        else:
            t = "No information is available for: {}".format(find)
            self.parent()._description.setText(t)


class InputDialog(QtWidgets.QDialog):
    """Input Dialog
    """

    def __init__(self, *args):

        QtWidgets.QDialog.__init__(self, *args)

        # Set size
        size = 650, 190
        offset = 0
        size2 = size[0], size[1] + offset
        self.resize(*size2)
        self.setMaximumSize(*size2)
        self.setMinimumSize(*size2)
        # self.item = ""

        # Arguments
        self._argument_info = QtWidgets.QTextEdit(self)
        self._argument_info.setStyleSheet("QTextEdit { background:#ddd; }")
        self._argument_info.setToolTip("Arguments")
        self._argument_info.setReadOnly(True)
        #
        self._argument = QtWidgets.QLineEdit(self)
        self._argument.setReadOnly(False)
        self._argument.setPlaceholderText('"string", 1, variable')
        tip = 'Add argument:\n"NAME" = object.getByName("NAME"),\n 0 = object.getByIndex(0),\n variable = object.createMethod(variable)'
        self._argument.setToolTip(tip)
        #
        layout_1 = QtWidgets.QVBoxLayout()
        layout_1.addWidget(self._argument_info, 0)
        layout_1.addWidget(self._argument, 0)

        # Buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout_2 = QtWidgets.QHBoxLayout()
        layout_2.addWidget(self.button_box, 0)

        # Layouts
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.addLayout(layout_1, 0)
        mainLayout.addLayout(layout_2, 0)
        self.setLayout(mainLayout)
