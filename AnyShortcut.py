#Author-Thomas Axelsson
#Description-Shows a menu that let's you assign shortcuts to your last run commands.

# This file is part of AnyShortcut, a Fusion 360 add-in for assigning
# shortcuts to the last run commands.
#
# Copyright (c) 2020 Thomas Axelsson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import adsk.core, adsk.fusion, adsk.cam

from collections import deque
import os

NAME = 'AnyShortcut'
FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Import relative path to avoid namespace pollution
from .thomasa88lib import utils, events, manifest, error, timeline as libTimeLine
utils.ReImport_List(events, manifest, error, libTimeLine, utils)
# def newID(idVal): return 


ENABLE_CMD_DEF_ID = 'thomasa88_anyShortcutList'
PANEL_ID = 'thomasa88_anyShortcutPanel'
MAIN_DROPDOWN_ID = 'thomasa88_anyShortcutMainDropdown'
TRACKING_DROPDOWN_ID = 'thomasa88_anyShortcutDropdown'
BUILTIN_DROPDOWN_ID = 'thomasa88_anyShortcutPremadeDropdown'

app_:adsk.core.Application = None
ui_:adsk.core.UserInterface = None
error_catcher_ = error.ErrorCatcher()
events_manager_ = events.EventsManager(error_catcher_)
manifest_ = manifest.read()
command_starting_handler_info_ = None

panel_:adsk.core.ToolbarPanel = None
tracking_dropdown_:adsk.core.DropDownControl = None
builtin_dropdown_:adsk.core.DropDownControl = None
enable_cmd_def_:adsk.core.CommandDefinition = None
HISTORY_LENGTH = 10
cmd_def_history_ = deque()
# Keeping info in a separate container, as the search is much faster
# if we can do cmd_def in cmd_def_history, not making the GUI sluggish.
cmd_controls_ = deque()
MAX_TRACK = 10
track_count_ = 0
tracking_ = False

termination_funcs_ = []
termination_handler_info_ = None



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def ifDelete(obj): return obj.deleteMe() if obj and obj.isValid else False
def deleteAll(*objs): return all([ifDelete(obj) for obj in objs])
def executeCommand(cmdName): ui_.commandDefinitions.itemById(cmdName).execute()


def UpdateButton(cmdDef: adsk.core.CommandDefinition,Title,Icon):
	cmdDef.resourceFolder = Icon
	cmdDef.controlDefinition.name = Title

# Commands without icons cannot have shortcuts, so add one if needed. 
# Maybe because the "Pin to" options in the same menu would fail?
# Creds to u/lf_1 on reddit.
def checkIcon(cmdDef:adsk.core.CommandDefinition, noIconPath:str = './resources/noicon'):
	try: 
		if not cmdDef.resourceFolder: cmdDef.resourceFolder = noIconPath
	except: cmdDef.resourceFolder = noIconPath

def tryIcon(cmdDef:adsk.core.CommandDefinition, noIconPath:str = './resources/noicon'):
	try: testAccess = cmdDef.resourceFolder
	except: cmdDef.resourceFolder = noIconPath


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def start_tracking():
	global tracking_, track_count_
	global command_starting_handler_info_
	tracking_ = True
	track_count_ = 0
	command_starting_handler_info_ = events_manager_.add_handler(ui_.commandStarting, callback=command_starting_handler)
	update_enable_text()

def stop_tracking():
	global tracking_
	tracking_ = False
	events_manager_.remove_handler(command_starting_handler_info_)
	update_enable_text()


def update_enable_text():
	if tracking_:
		text = f'Stop recording (Auto-stop after {MAX_TRACK-track_count_} more commands)'
		icon = './resources/stop'
	else:
		text = f'Start recording (Auto-stop after {MAX_TRACK} unique commands)'
		icon = './resources/record'
	UpdateButton(enable_cmd_def_, text, icon)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def enable_cmd_def__created_handler(args: adsk.core.CommandCreatedEventArgs):
	events_manager_.add_handler(args.command.execute, callback=enable_command_execute_handler)

def enable_command_execute_handler(args):
	if not tracking_: start_tracking()
	else: stop_tracking()
	
def command_starting_handler(args:adsk.core.ApplicationCommandEventArgs):
	global track_count_
	print("STARTING", args.commandId)
	cmd_def = args.commandDefinition
	if cmd_def == enable_cmd_def_: return # Skip ourselves
	
	if cmd_def not in cmd_def_history_:
		while len(cmd_def_history_) >= HISTORY_LENGTH:
			cmd_def_history_.popleft()
			cmd_controls_.popleft().deleteMe()
		
		print("ADD")
		tryIcon(cmd_def, './resources/noicon')
		cmd_control = tracking_dropdown_.controls.addCommand(cmd_def)
		if cmd_control:
			cmd_def_history_.append(cmd_def)
			cmd_controls_.append(cmd_control)

			track_count_ += 1
			update_enable_text()

			if track_count_ >= MAX_TRACK: ()
		else: print("ADD FAIL", cmd_def.execute)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def look_at_sketch_handler(args: adsk.core.CommandCreatedEventArgs):
	# Look at is usually not added to the history - skip execution.
	# Avoid getting listed as a repeatable command.
	args.command.isRepeatable = False
	edit_object = app_.activeEditObject
	if edit_object.classType() == 'adsk::fusion::Sketch':
		# laughingcreek provided the way that Fusion actually does this "Look At"
		# https://forums.autodesk.com/t5/fusion-360-design-validate/shortcut-for-look-at/m-p/9517669/highlight/true#M217044
		ui_.activeSelections.clear()
		ui_.activeSelections.add(edit_object)
		executeCommand('LookAtCommand')

		# We must give the Look At command time to run. This seems to imitate the way that Fusion does it.
		# Using lambda to get fresh/valid instance of activeSelections at the end of the wait.
		on_command_terminate('LookAtCommand', adsk.core.CommandTerminationReason.CancelledTerminationReason, lambda: ui_.activeSelections.clear())

def look_at_sketch_or_selected_handler(args: adsk.core.CommandCreatedEventArgs):
	# Look at is usually not added to the history - skip execution handler.
	# Avoid getting listed as a repeatable command.
	args.command.isRepeatable = False
	if ui_.activeSelections.count == 0:
		edit_object = app_.activeEditObject
		if edit_object.classType() == 'adsk::fusion::Sketch': look_at_sketch_handler(args)
	else: executeCommand('LookAtCommand')

def activate_containing_component_handler(args: adsk.core.CommandCreatedEventArgs):
	args.command.isRepeatable = False
	if ui_.activeSelections.count == 1:
		selected = ui_.activeSelections[0].entity
		if selected.classType() not in ['adsk::fusion::Component', 'adsk::fusion::Occurrence']:
			ui_.activeSelections.clear() # Component not selected. Select the component.
			if selected.assemblyContext is None:
				ui_.activeSelections.add(app_.activeProduct.rootComponent) # Root component
			else: ui_.activeSelections.add(selected.assemblyContext)
		executeCommand('FusionActivateLocalCompCmd')
		executeCommand('FindInBrowser')

def repeat_command_handler(args: adsk.core.CommandCreatedEventArgs):
	# Avoid getting picked up and repeated into eternity
	args.command.isRepeatable = False
	args.command.isExecutedWhenPreEmpted = False
	executeCommand('RepeatCommand')

def alignViewHandler(args: adsk.core.CommandCreatedEventArgs):
	# Avoid getting picked up and repeated into eternity
	args.command.isRepeatable = False
	args.command.isExecutedWhenPreEmpted = False
	executeCommand('LookAtCommand')
	adsk.doEvents()

	upLine = ui_.selectEntity('Please select a line represinting the "up" direction', 'LinearEdges,SketchLines,ConstructionLines').entity
	if isinstance(upLine, adsk.fusion.BRepEdge):
		start = upLine.startVertex.geometry
		end = upLine.endVertex.geometry
		lineDirection = start.vectorTo(end)
	elif isinstance(upLine, adsk.fusion.SketchLine):
		start = upLine.startSketchPoint.geometry
		end = upLine.endSketchPoint.geometry
		lineDirection = start.vectorTo(end)
	elif isinstance(upLine, adsk.fusion.ConstructionAxis):
		infLine = upLine.geometry
		lineDirection = infLine.direction

	camera_copy = app_.activeViewport.camera
	camera_copy.upVector = lineDirection
	camera_copy.isSmoothTransition = True
	app_.activeViewport.camera = camera_copy
	adsk.doEvents()
	ui_.activeSelections.clear()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def create_roll_history_handler(move_function_name):
	# Cannot use select + the native FusionRollCommand, due to this bug (2020-08-02):
	# https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-object-in-component-using-activeselections/m-p/9653216

	def execute_handler(args: adsk.core.CommandEventArgs):
		timeline_status, timeline = libTimeLine.get_timeline()
		if timeline_status != timeline.TIMELINE_STATUS_OK:
			args.executeFailed = True
			args.executeFailedMessage = 'Failed to get the timeline'
			return
		move_function = getattr(timeline, move_function_name)
		move_function()

	def created_handler(args: adsk.core.CommandCreatedEventArgs):
		args.command.isRepeatable = False
		events_manager_.add_handler(args.command.execute, callback=execute_handler)
	return created_handler

def create_view_orientation_handler(view_orientation_name, smooth=False, fitView = False):
	def created_handler(args: adsk.core.CommandCreatedEventArgs):
		# We don't want undo history, so no execute handler
		# Avoid getting listed as a repeatable command.
		args.command.isRepeatable = False

		camera_copy = app_.activeViewport.camera
		camera_copy.viewOrientation = getattr(adsk.core.ViewOrientations, view_orientation_name + 'ViewOrientation')
		# camera_copy.isFitView = fitView
		# camera_copy.isSmoothTransition = smooth
		app_.activeViewport.camera = camera_copy
	return created_handler
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def on_command_terminate(command_id, termination_reason, func):
	global termination_handler_info_
	if not termination_handler_info_:
		termination_handler_info_ = events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)
	termination_funcs_.append((command_id, termination_reason, func))   

def command_terminated_handler(args:adsk.core.ApplicationCommandEventArgs):
	global termination_handler_info_
	remove_indices = []
	for i, (command_id, termination_reason, func) in enumerate(termination_funcs_):
		if (command_id == args.commandId and (termination_reason is None or termination_reason == args.terminationReason)):
			remove_indices.append(i)
			func()
	
	for i in reversed(remove_indices): del termination_funcs_[i]

	if len(termination_funcs_) == 0:
		events_manager_.remove_handler(termination_handler_info_)
		termination_handler_info_ = None

def add_builtin_dropdown(parent:adsk.core.ToolbarPanel):
	global builtin_dropdown_
	ifDelete(parent.controls.itemById(BUILTIN_DROPDOWN_ID))
	builtin_dropdown_ = parent.controls.addDropDown(f'Built-in Commands',
													'./resources/builtin',
													BUILTIN_DROPDOWN_ID)

	def create(cmd_def_id, text, tooltip, resource_folder, handler):
		# The cmd_def_id must never change during development of the add-in
		# as users hotkeys will map to the command definition ID.
		ifDelete(ui_.commandDefinitions.itemById(cmd_def_id))
		cmd_def = ui_.commandDefinitions.addButtonDefinition( cmd_def_id, text, tooltip, resource_folder)
		checkIcon(cmd_def) # Must have icon for the assign shortcut menu to appear

		events_manager_.add_handler(cmd_def.commandCreated, callback=handler)
		return cmd_def

	c = create('thomasa88_anyShortcutListLookAtSketchCommand',
				'Look At Sketch',
				'Rotates the view to look at the sketch currently being edited. ' + 
				'No action is performed if a sketch is not being edited.',
				'./resources/lookatsketch',
				look_at_sketch_handler)
	builtin_dropdown_.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListLookAtSketchOrSelectedCommand',
				'Look At Selected or Sketch',
				'Rotates the view to look at, in priority order:\n' +
				' 1. The selected object, if any\n' +
				' 2. The sketch being edited',
				'./resources/lookatselectedorsketch',
				look_at_sketch_or_selected_handler)
	builtin_dropdown_.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListActivateContainingOrComponentCommand',
				'Activate (containing) Component',
				'Activates the selected component. If no component is selected, '
				+ 'the component directly containing the selected object is activated.',
				'./resources/activate',
				activate_containing_component_handler)
	builtin_dropdown_.controls.addCommand(c)

	# For some reason, repeat captured using the tracking only works when clicking,
	# not with a keyboard shortcut.
	c = create('thomasa88_anyShortcutBuiltinRepeatCommand',
				'Repeat Last Command',
				'',
				'./resources/repeat',
				repeat_command_handler)
	builtin_dropdown_.controls.addCommand(c)
	
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	c = create('thomasa88_anyShortcutBuiltinAlignView',
				'Align The Camera',
				'',
				'./resources/repeat',
				alignViewHandler)
	builtin_dropdown_.controls.addCommand(c)

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	timeline_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('Timeline', './resources/timeline',
															   'thomasa88_anyShortcutBuiltinTimelineList')

	c = create('thomasa88_anyShortcutListRollToBeginning',
				'Roll History Marker to Beginning',
				'',
				'./resources/timelinebeginning',
				create_roll_history_handler('moveToBeginning'))
	timeline_dropdown.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListRollBack',
				'Roll History Marker Back',
				'',
				'./resources/timelineback',
				create_roll_history_handler('moveToPreviousStep'))
	timeline_dropdown.controls.addCommand(c)
	
	c = create('thomasa88_anyShortcutListRollForward',
				'Roll History Marker Forward',
				'',
				'./resources/timelineforward',
				create_roll_history_handler('movetoNextStep'))
	timeline_dropdown.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListRollToEnd',
			   'Roll History Marker to End',
			   '',
			   './resources/timelineend',
			   create_roll_history_handler('moveToEnd'))
	timeline_dropdown.controls.addCommand(c)

	# timeline.play() just seems to skip to the end. Disabled.
	# c = create('thomasa88_anyShortcutListHistoryPlay',
	#     'Play History from Current Position',
	#     '',
	#     './resources/timelineplay',
	#     create_roll_history_handler('play'))
	# timeline_dropdown.controls.addCommand(c)

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	view_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('View Orientation', './resources/viewfront', 'thomasa88_anyShortcutBuiltinViewList')
	for view in ['Front', 'Back', 'Top', 'Bottom', 'Left', 'Right']:
		c = create('thomasa88_anyShortcutBuiltinView' + view,
			'View ' + view, '',
			'./resources/view' + view.lower(),
			create_view_orientation_handler(view))
		view_dropdown.controls.addCommand(c)
		
	view_corner_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('View Corner', './resources/viewisotopright', 'thomasa88_anyShortcutBuiltinCornerViewList')
	for view in ['IsoTopRight', 'IsoTopLeft','IsoBottomRight', 'IsoBottomLeft' ]:
		c = create('thomasa88_anyShortcutBuiltinCornerViewList' + view,
			'View ' + view.strip('Iso'), '',
			'./resources/view' + view.lower(),
			create_view_orientation_handler(view))
		view_corner_dropdown.controls.addCommand(c)
	# adsk.core.ViewOrientations.IsoTopRightViewOrientation
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
otherCreations = []

@error.CatchErrors
def run(context):
	global app_, ui_
	global tracking_dropdown_
	global panel_
	app_,ui_ = utils.AppObjects()
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Add the command to the tab.
	panels = ui_.allToolbarTabs.itemById('ToolsTab').toolbarPanels

	ifDelete(panels.itemById(PANEL_ID))
	panel_ = panels.add(PANEL_ID, f'{NAME}')

	add_builtin_dropdown(panel_)

	ifDelete(panel_.controls.itemById(TRACKING_DROPDOWN_ID))
	tracking_dropdown_ = panel_.controls.addDropDown(f'Command Recorder',
														'./resources/tracker',
														TRACKING_DROPDOWN_ID)
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	global enable_cmd_def_
	ifDelete(ui_.commandDefinitions.itemById(ENABLE_CMD_DEF_ID))
	# Cannot get checkbox to play nicely (won't update without collapsing
	# the menu and the default checkbox icon is not showing...).  See checkbox-test branch.
	enable_cmd_def_ = ui_.commandDefinitions.addButtonDefinition(
												ENABLE_CMD_DEF_ID,
												f'Loading...', '')
	update_enable_text()
	events_manager_.add_handler(event=enable_cmd_def_.commandCreated, callback=enable_cmd_def__created_handler)
	
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	enable_control:adsk.core.CommandControl = tracking_dropdown_.controls.addCommand(enable_cmd_def_)
	enable_control.isPromoted = True
	enable_control.isPromotedByDefault = True
	tracking_dropdown_.controls.addSeparator()








@error.CatchErrors
def stop(context):
	events_manager_.clean_up()
	deleteAll(tracking_dropdown_, builtin_dropdown_, panel_, *otherCreations)
	# Need to delete children?






































	# ui_.messageBox(str(camDict))

	# app_.activeViewport.camera.viewOrientation = adsk.core.ViewOrientations.BackViewOrientation
	# app_.activeViewport.camera.viewOrientation = adsk.fusion.ViewCorners.upperLeftViewCorner



	# ui_.messageBox(str(app_.activeViewport.camera)) 
	
	# global builtin_dropdown_
	# FINDWINDOWCMD = 'FindInWindow'
	# FINDBROWSERCMD = 'FindInBrowser'
	# windowCmdDef = ui_.commandDefinitions.itemById(FINDWINDOWCMD)
	# browserCmdDef = ui_.commandDefinitions.itemById(FINDBROWSERCMD)

	# checkIcon(windowCmdDef)
	# otherCreations.append( builtin_dropdown_.controls.addCommand(windowCmdDef) )

	# checkIcon(browserCmdDef)
	# otherCreations.append( builtin_dropdown_.controls.addCommand(browserCmdDef) )


	# des:adsk.fusion.Design= app_.activeProduct
	# root:adsk.core.Attribute = dict(des.rootComponent.attributes)
	# root = [des.rootComponent.attributes.item(i) for i in range(des.rootComponent.attributes.count)]


	# occs:adsk.fusion.OccurrenceList = root.occurrences.asList
	# occNames =[occ.name for occ in occs]
	# ui_.messageBox(str(root))
	# ui_.messageBox(str(len(root)))




	# FINDHOME = 'FitCommand'
	# fitCommand = ui_.commandDefinitions.itemById(FINDHOME)
	# fitCommand.execute()

	# des:adsk.fusion.Design= app_.activeProduct
	# root = des.rootComponent
	# origin = root.originConstructionPoint.geometry


	# # camera_copy:adsk.core.Camera = app_.activeViewport.camera
	# # camera_copy.target = origin
	# # camera_copy.isFitView = True
	# # camera_copy.isSmoothTransition = True
	# # app_.activeViewport.camera = camera_copy
	# # adsk.doEvents()
	
	# camera_copy:adsk.core.Camera = app_.activeViewport.camera
	# camera_copy.isFitView = True
	# camera_copy.isSmoothTransition = True
	# app_.activeViewport.camera = camera_copy
	# camera_copy:adsk.core.Camera = app_.activeViewport.camera
	# camera_copy.target = origin
	# camera_copy.viewOrientation = adsk.core.ViewOrientations.IsoTopRightViewOrientation
	# camera_copy.isSmoothTransition = True
	# app_.activeViewport.camera = camera_copy


	# adsk.doEvents()
	# camera_copy = app_.activeViewport.camera
	# camera_copy.isFitView = True
	# camera_copy.isSmoothTransition = True
	# app_.activeViewport.camera = camera_copy


	# des:adsk.fusion.Design= app_.activeProduct
	# root = des.rootComponent
	# origin = root.originConstructionPoint.geometry
	# adsk.doEvents()

	# camera_copy = app_.activeViewport.camera
	# camera_copy.target = origin
	# camera_copy.isSmoothTransition = True
	# app_.activeViewport.camera = camera_copy





	# des:adsk.fusion.Design= app_.activeProduct
	# root = des.rootComponent
	# origin = root.originConstructionPoint

	# selectionOld = ui_.activeSelections.all
	# ui_.activeSelections.clear()
	# ui_.activeSelections.add(root.originConstructionPoint)
	# windowCmdDef.execute()
	# ui_.activeSelections.clear()
	# [ui_.activeSelections.add(selection) for selection in selectionOld]













"""#Author-Thomas Axelsson
#Description-Shows a menu that let's you assign shortcuts to your last run commands.

# This file is part of AnyShortcut, a Fusion 360 add-in for assigning
# shortcuts to the last run commands.
#
# Copyright (c) 2020 Thomas Axelsson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import adsk.core, adsk.fusion, adsk.cam, traceback

from collections import deque
import math
import os
import threading
import time

NAME = 'AnyShortcut'
FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Import relative path to avoid namespace pollution
from .thomasa88lib import utils
from .thomasa88lib import events
from .thomasa88lib import manifest
from .thomasa88lib import error
from .thomasa88lib import timeline

# Force modules to be fresh during development
import importlib
import thomasa88lib
importlib.reload(thomasa88lib.utils)
importlib.reload(thomasa88lib.events)
importlib.reload(thomasa88lib.manifest)
importlib.reload(thomasa88lib.error)
importlib.reload(thomasa88lib.timeline)

ENABLE_CMD_DEF_ID = 'thomasa88_anyShortcutList'
PANEL_ID = 'thomasa88_anyShortcutPanel'
MAIN_DROPDOWN_ID = 'thomasa88_anyShortcutMainDropdown'
TRACKING_DROPDOWN_ID = 'thomasa88_anyShortcutDropdown'
BUILTIN_DROPDOWN_ID = 'thomasa88_anyShortcutPremadeDropdown'

app_:adsk.core.Application = None
ui_:adsk.core.UserInterface = None
error_catcher_ = error.ErrorCatcher()
events_manager_ = events.EventsManager(error_catcher_)
manifest_ = manifest.read()
command_starting_handler_info_ = None

panel_ = None
tracking_dropdown_ = None
builtin_dropdown_ = None
enable_cmd_def_ = None
HISTORY_LENGTH = 10
cmd_def_history_ = deque()
# Keeping info in a separate container, as the search is much faster
# if we can do cmd_def in cmd_def_history, not making the GUI sluggish.
cmd_controls_ = deque()
MAX_TRACK = 10
track_count_ = 0
tracking_ = False

termination_funcs_ = []
termination_handler_info_ = None


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def deleteIf(obj):obj.deleteMe() if obj else None
def getUiItem(itemID):return ui_.commandDefinitions.itemById(itemID)




#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~





def command_starting_handler(event_args:adsk.core.ApplicationCommandEventArgs):

	print("STARTING", event_args.commandId)
	cmd_def = event_args.commandDefinition
	if cmd_def == enable_cmd_def_: return# Skip ourselves
	if cmd_def not in cmd_def_history_:
		while len(cmd_def_history_) >= HISTORY_LENGTH:
			cmd_def_history_.popleft()
			cmd_controls_.popleft().deleteMe()
		
		print("ADD")
		# Commands without icons cannot have shortcuts, so add
		# one if needed. Maybe because the "Pin to" options in
		# the same menu would fail?
		# Creds to u/lf_1 on reddit.
		try: res_folder = cmd_def.resourceFolder
		except: cmd_def.resourceFolder = './resources/noicon'

		cmd_control = tracking_dropdown_.controls.addCommand(cmd_def)
		if cmd_control:
			cmd_def_history_.append(cmd_def)
			cmd_controls_.append(cmd_control)

			global track_count_
			track_count_ += 1
			update_enable_text()

			if track_count_ >= MAX_TRACK: stop_tracking()
		else: print("ADD FAIL", cmd_def.execute)

def enable_cmd_def__created_handler(args: adsk.core.CommandCreatedEventArgs):
	events_manager_.add_handler(args.command.execute, callback=enable_command_execute_handler)

def enable_command_execute_handler(args):
	global tracking_
	if not tracking_: start_tracking()
	else: stop_tracking()

def start_tracking():
	global tracking_
	global track_count_
	global command_starting_handler_info_
	tracking_ = True
	track_count_ = 0
	command_starting_handler_info_ = events_manager_.add_handler(ui_.commandStarting, callback=command_starting_handler)
	update_enable_text()

def stop_tracking():
	global tracking_
	tracking_ = False
	events_manager_.remove_handler(command_starting_handler_info_)
	update_enable_text()

def update_enable_text():
	if tracking_:
		text = f'Stop recording (Auto-stop after {MAX_TRACK - track_count_} more commands)'
		enable_cmd_def_.resourceFolder = './resources/stop'
	else:
		text = f'Start recording (Auto-stop after {MAX_TRACK} unique commands)'
		enable_cmd_def_.resourceFolder = './resources/record'
	enable_cmd_def_.controlDefinition.name = text

def look_at_sketch_handler(args: adsk.core.CommandCreatedEventArgs):
	# Look at is usually not added to the history - skip execution.
	# Avoid getting listed as a repeatable command.
	args.command.isRepeatable = False
	edit_object = app_.activeEditObject
	if edit_object.classType() == 'adsk::fusion::Sketch':
		# laughingcreek provided the way that Fusion actually does this "Look At"
		# https://forums.autodesk.com/t5/fusion-360-design-validate/shortcut-for-look-at/m-p/9517669/highlight/true#M217044
		ui_.activeSelections.clear()
		ui_.activeSelections.add(edit_object)
		getUiItem('LookAtCommand').execute()

		# We must give the Look At command time to run. This seems to imitate the
		# way that Fusion does it.
		# Using lambda to get fresh/valid instance of activeSelections at the end of
		# the wait.
		on_command_terminate('LookAtCommand', adsk.core.CommandTerminationReason.CancelledTerminationReason,
							 lambda: ui_.activeSelections.clear())
		#events_manager_.delay(lambda: ui_.activeSelections.clear(), secs=1)

def look_at_sketch_or_selected_handler(args: adsk.core.CommandCreatedEventArgs):
	# Look at is usually not added to the history - skip execution handler.
	# Avoid getting listed as a repeatable command.
	args.command.isRepeatable = False
	if ui_.activeSelections.count == 0:
		edit_object = app_.activeEditObject
		if edit_object.classType() == 'adsk::fusion::Sketch':
			look_at_sketch_handler(args)
	else: getUiItem('LookAtCommand').execute()

def activate_containing_component_handler(args: adsk.core.CommandCreatedEventArgs):
	args.command.isRepeatable = False
	if ui_.activeSelections.count == 1:
		selected = ui_.activeSelections[0].entity
		if selected.classType() not in ['adsk::fusion::Component', 'adsk::fusion::Occurrence']:
			# Component not selected. Select the component.
			ui_.activeSelections.clear()
			if selected.assemblyContext is None:
				# Root component
				ui_.activeSelections.add(app_.activeProduct.rootComponent)
			else: ui_.activeSelections.add(selected.assemblyContext)
		getUiItem('FusionActivateLocalCompCmd').execute()
		getUiItem('FindInBrowser').execute()

def repeat_command_handler(args: adsk.core.CommandCreatedEventArgs):
	# Avoid getting picked up and repeated into eternity
	args.command.isRepeatable = False
	args.command.isExecutedWhenPreEmpted = False
	getUiItem('RepeatCommand').execute()

def create_roll_history_handler(move_function_name):
	# Cannot use select + the native FusionRollCommand, due to this bug (2020-08-02):
	# https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-object-in-component-using-activeselections/m-p/9653216

	def execute_handler(args: adsk.core.CommandEventArgs):
		timeline_status, timeline = thomasa88lib.timeline.get_timeline()
		if timeline_status != thomasa88lib.timeline.TIMELINE_STATUS_OK:
			args.executeFailed = True
			args.executeFailedMessage = 'Failed to get the timeline'
			return
		move_function = getattr(timeline, move_function_name)
		move_function()

	def created_handler(args: adsk.core.CommandCreatedEventArgs):
		args.command.isRepeatable = False
		events_manager_.add_handler(args.command.execute, callback=execute_handler)
	return created_handler

def create_view_orientation_handler(view_orientation_name):
	def created_handler(args: adsk.core.CommandCreatedEventArgs):
		# We don't want undo history, so no execute handler
		
		# Avoid getting listed as a repeatable command.
		args.command.isRepeatable = False

		camera_copy = app_.activeViewport.camera
		camera_copy.cameraType = adsk.core.CameraTypes.OrthographicCameraType #?
		camera_copy.viewOrientation = getattr(adsk.core.ViewOrientations, view_orientation_name + 'ViewOrientation')
		app_.activeViewport.camera = camera_copy

		# Must set the up vector after the orient rotation has been performed,
		# with a delay, for it to work correctly.

		# def rotate_up():
		#     camera_copy = app_.activeViewport.camera
		#     # defaultModelingOrientation does not give us the orientation for
		#     # the current document.
		#     # ---> We don't know which direction is up!
		#     # Create duplicate sets of commands?
		#     modeling_orientation = app_.preferences.generalPreferences.defaultModelingOrientation

		#     # Z-Up orientation:
		#     if view_orientation_name in ['Top', 'Bottom']:
		#         up = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
		#     else:
		#         up = adsk.core.Vector3D.create(0.0, 0.0, 1.0)
			
		#     if camera_copy.upVector.angleTo(up) > (math.pi / 4.0):
		#         camera_copy.upVector = up
		#         app_.activeViewport.camera = camera_copy
		#     #app_.activeViewport.refresh() Use this?
		
		#events_manager_.delay(rotate_up, secs=1)

	return created_handler

def on_command_terminate(command_id, termination_reason, func):
	global termination_handler_info_
	if not termination_handler_info_:
		termination_handler_info_ = events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)
	termination_funcs_.append((command_id, termination_reason, func))   

def command_terminated_handler(args:adsk.core.ApplicationCommandEventArgs):
	global termination_handler_info_
	
	#print("TERM", args.commandId, args.terminationReason, app_.activeEditObject.classType())
	
	remove_indices = []
	for i, (command_id, termination_reason, func) in enumerate(termination_funcs_):
		if (command_id == args.commandId and (termination_reason is None or termination_reason == args.terminationReason)):
			remove_indices.append(i); func()
	for i in reversed(remove_indices): del termination_funcs_[i]
	if len(termination_funcs_) == 0:
		events_manager_.remove_handler(termination_handler_info_)
		termination_handler_info_ = None

def add_builtin_dropdown(parent:adsk.core.DropDownControl):
	global builtin_dropdown_
	deleteIf(parent.controls.itemById(BUILTIN_DROPDOWN_ID))
	builtin_dropdown_ = parent.controls.addDropDown(f'Built-in Commands',
													'./resources/builtin',
													BUILTIN_DROPDOWN_ID)

	def create(cmd_def_id, text, tooltip, resource_folder, handler):
		# The cmd_def_id must never change during development of the add-in
		# as users hotkeys will map to the command definition ID.
		deleteIf(getUiItem(cmd_def_id))
		cmd_def = ui_.commandDefinitions.addButtonDefinition(cmd_def_id, text, tooltip, resource_folder)
		# Must have icon for the assign shortcut menu to appear
		if not resource_folder: cmd_def.resourceFolder = './resources/noicon'
		
		events_manager_.add_handler(cmd_def.commandCreated, callback=handler)
		return cmd_def

	c = create('thomasa88_anyShortcutListLookAtSketchCommand',
				'Look At Sketch',
				'Rotates the view to look at the sketch currently being edited. ' + 
				'No action is performed if a sketch is not being edited.',
				'./resources/lookatsketch',
				look_at_sketch_handler)
	builtin_dropdown_.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListLookAtSketchOrSelectedCommand',
				'Look At Selected or Sketch',
				'Rotates the view to look at, in priority order:\n' +
				' 1. The selected object, if any\n' +
				' 2. The sketch being edited',
				'./resources/lookatselectedorsketch',
				look_at_sketch_or_selected_handler)
	builtin_dropdown_.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListActivateContainingOrComponentCommand',
				'Activate (containing) Component',
				'Activates the selected component. If no component is selected, '
				+ 'the component directly containing the selected object is activated.',
				'./resources/activate',
				activate_containing_component_handler)
	builtin_dropdown_.controls.addCommand(c)

	# For some reason, repeat captured using the tracking only works when clicking,
	# not with a keyboard shortcut.
	c = create('thomasa88_anyShortcutBuiltinRepeatCommand',
				'Repeat Last Command',
				'',
				'./resources/repeat',
				repeat_command_handler)
	builtin_dropdown_.controls.addCommand(c)

	timeline_dropdown = builtin_dropdown_.controls.addDropDown('Timeline', './resources/timeline',
															   'thomasa88_anyShortcutBuiltinTimelineList')

	c = create('thomasa88_anyShortcutListRollToBeginning',
				'Roll History Marker to Beginning',
				'',
				'./resources/timelinebeginning',
				create_roll_history_handler('moveToBeginning'))
	timeline_dropdown.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListRollBack',
				'Roll History Marker Back',
				'',
				'./resources/timelineback',
				create_roll_history_handler('moveToPreviousStep'))
	timeline_dropdown.controls.addCommand(c)
	
	c = create('thomasa88_anyShortcutListRollForward',
				'Roll History Marker Forward',
				'',
				'./resources/timelineforward',
				create_roll_history_handler('movetoNextStep'))
	timeline_dropdown.controls.addCommand(c)

	c = create('thomasa88_anyShortcutListRollToEnd',
			   'Roll History Marker to End',
			   '',
			   './resources/timelineend',
			   create_roll_history_handler('moveToEnd'))
	timeline_dropdown.controls.addCommand(c)

	# timeline.play() just seems to skip to the end. Disabled.
	# c = create('thomasa88_anyShortcutListHistoryPlay',
	#     'Play History from Current Position',
	#     '',
	#     './resources/timelineplay',
	#     create_roll_history_handler('play'))
	# timeline_dropdown.controls.addCommand(c)

	view_dropdown = builtin_dropdown_.controls.addDropDown('View Orientation', './resources/viewfront','thomasa88_anyShortcutBuiltinViewList')
	for view in ['Front', 'Back', 'Top', 'Bottom', 'Left', 'Right']:
		c = create('thomasa88_anyShortcutBuiltinView' + view,
			'View ' + view, '',
			'./resources/view' + view.lower(),
			create_view_orientation_handler(view))
		view_dropdown.controls.addCommand(c)

def run(context):
	global app_
	global ui_
	global tracking_dropdown_
	global builtin_dropdown_
	global panel_
	global enable_cmd_def_
	with error_catcher_:
		app_:adsk.core.Application = adsk.core.Application.get()
		ui_ = app_.userInterface

		# Add the command to the tab.
		tab = ui_.allToolbarTabs.itemById('ToolsTab')
		deleteIf(tab.toolbarPanels.itemById(PANEL_ID))
		panel_ = tab.toolbarPanels.add(PANEL_ID, f'{NAME}')
		add_builtin_dropdown(panel_)

		tracking_dropdown_ = panel_.controls.itemById(TRACKING_DROPDOWN_ID)
		if tracking_dropdown_: tracking_dropdown_.deleteMe()
		
		tracking_dropdown_ = panel_.controls.addDropDown(f'Command Recorder',
														 './resources/tracker',
														 TRACKING_DROPDOWN_ID)

		deleteIf(getUiItem(ENABLE_CMD_DEF_ID))

		# Cannot get checkbox to play nicely (won't update without collapsing
		# the menu and the default checkbox icon is not showing...).
		# See checkbox-test branch.
		enable_cmd_def_ = ui_.commandDefinitions.addButtonDefinition(ENABLE_CMD_DEF_ID, f'Loading...', '')
		update_enable_text()
		events_manager_.add_handler(event=enable_cmd_def_.commandCreated, callback=enable_cmd_def__created_handler)
		
		enable_control = tracking_dropdown_.controls.addCommand(enable_cmd_def_)
		enable_control.isPromoted = True
		enable_control.isPromotedByDefault = True
		tracking_dropdown_.controls.addSeparator()

def stop(context):
	with error_catcher_:
		events_manager_.clean_up()
		tracking_dropdown_.deleteMe()
		builtin_dropdown_.deleteMe()
		panel_.deleteMe()

		# Need to delete children?

"""

