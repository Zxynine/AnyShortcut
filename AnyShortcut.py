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
	cmd_def = args.commandDefinition
	if cmd_def == enable_cmd_def_: return # Skip ourselves
	
	if cmd_def not in cmd_def_history_:
		while len(cmd_def_history_) >= HISTORY_LENGTH:
			cmd_def_history_.popleft()
			cmd_controls_.popleft().deleteMe()
		
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

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@error.CatchErrors
def run(context):
	global app_, ui_
	global panel_
	app_,ui_ = utils.AppObjects()
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Add the command to the tab.
	panels = ui_.allToolbarTabs.itemById('ToolsTab').toolbarPanels

	ifDelete(panels.itemById(PANEL_ID))
	panel_ = panels.add(PANEL_ID, f'{NAME}')
	add_builtin_dropdown(panel_)
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	global tracking_dropdown_
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
	deleteAll(tracking_dropdown_, builtin_dropdown_, panel_)
	# Need to delete children?




#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def look_at_sketch_handler(args: adsk.core.CommandCreatedEventArgs):
	# Look at is usually not added to the history - skip execution.
	# Avoid getting listed as a repeatable command.
	args.command.isRepeatable = False
	edit_object = app_.activeEditObject
	if isinstance(edit_object, adsk.fusion.Sketch):
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
		look_at_sketch_handler(args)
	else: executeCommand('LookAtCommand')

def activate_containing_component_handler(args: adsk.core.CommandCreatedEventArgs):
	args.command.isRepeatable = False
	if ui_.activeSelections.count == 1:
		selected = ui_.activeSelections[0].entity
		if not isinstance(selected, (adsk.fusion.Component, adsk.fusion.Occurrence)):
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





#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def getCameraDirection(camera:adsk.core.Camera):
	eye = camera.eye
	target = camera.target
	return eye.vectorTo(target)

def getLineDirection(line):
	if isinstance(line, adsk.fusion.BRepEdge):
		start = line.startVertex.geometry
		end = line.endVertex.geometry
		lineDirection = start.vectorTo(end)
	elif isinstance(line, adsk.fusion.SketchLine):
		start = line.startSketchPoint.geometry
		end = line.endSketchPoint.geometry
		lineDirection = start.vectorTo(end)
	elif isinstance(line, adsk.fusion.ConstructionAxis):
		infLine = line.geometry
		lineDirection = infLine.direction
	return lineDirection

def projectVectors(fromVec:adsk.core.Vector3D,toVec:adsk.core.Vector3D):
	dotProd = fromVec.dotProduct(toVec)
	sqrMag = fromVec.length**2

	projection = toVec.copy()
	projection.scaleBy(dotProd/sqrMag)
	return projection



def alignViewHandler(args: adsk.core.CommandCreatedEventArgs):
	# Avoid getting picked up and repeated into eternity
	args.command.isRepeatable = False
	args.command.isExecutedWhenPreEmpted = False
	executeCommand('LookAtCommand')
	adsk.doEvents()

	upLine = ui_.selectEntity('Please select a line represinting the "up" direction', 'LinearEdges,SketchLines,ConstructionLines').entity

	camera_copy = app_.activeViewport.camera
	camera_copy.upVector = getLineDirection(upLine)
	camera_copy.isSmoothTransition = True
	app_.activeViewport.camera = camera_copy
	adsk.doEvents()
	ui_.activeSelections.clear()


def changeViewAxis(args: adsk.core.CommandCreatedEventArgs):
	args.command.isRepeatable = False
	args.command.isExecutedWhenPreEmpted = False
	upLine = ui_.selectEntity('Please select a line represinting the "forwards" direction', 'LinearEdges,SketchLines,ConstructionLines').entity
	lineDirection = getLineDirection(upLine)
	cameraDirection = getCameraDirection(app_.activeViewport.camera)

	projection = projectVectors(cameraDirection,lineDirection)

	orintatedVector = projection.copy()
	orintatedVector.normalize()
	orintatedVector.scaleBy(cameraDirection.length)

	target = app_.activeViewport.camera.target
	newEye = target.asVector()
	newEye.subtract(orintatedVector)

	camera_copy = app_.activeViewport.camera
	camera_copy.eye = newEye.asPoint()
	camera_copy.target = target
	camera_copy.isSmoothTransition = True
	app_.activeViewport.camera = camera_copy

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def create_roll_history_handler(move_function_name):
	# Cannot use select + the native FusionRollCommand, due to this bug (2020-08-02):
	# https://forums.autodesk.com/t5/fusion-360-api-and-scripts/cannot-select-object-in-component-using-activeselections/m-p/9653216

	def execute_handler(args: adsk.core.CommandEventArgs):
		timeline_status, timeline = libTimeLine.get_timeline()
		if timeline_status != libTimeLine.TIMELINE_STATUS_OK:
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
		app_.activeViewport.camera = camera_copy
	return created_handler

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def add_builtin_dropdown(parent:adsk.core.ToolbarPanel):
	global builtin_dropdown_
	ifDelete(parent.controls.itemById(BUILTIN_DROPDOWN_ID))
	builtin_dropdown_ = parent.controls.addDropDown(f'Built-in Commands', './resources/builtin', BUILTIN_DROPDOWN_ID)

	def create(controls:adsk.core.ToolbarControls, cmd_def_id, text, tooltip, resource_folder, handler):
		# The cmd_def_id must never change during development of the add-in as users hotkeys will map to the command definition ID.
		ifDelete(ui_.commandDefinitions.itemById(cmd_def_id))
		cmd_def = ui_.commandDefinitions.addButtonDefinition( cmd_def_id, text, tooltip, resource_folder)
		checkIcon(cmd_def) # Must have icon for the assign shortcut menu to appear
		events_manager_.add_handler(cmd_def.commandCreated, callback=handler)
		return controls.addCommand(cmd_def)

	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutListLookAtSketchCommand',
			'Look At Sketch',
			'Rotates the view to look at the sketch currently being edited. ' + 
			'No action is performed if a sketch is not being edited.',
			'./resources/lookatsketch',
			look_at_sketch_handler)

	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutListLookAtSketchOrSelectedCommand',
			'Look At Selected or Sketch',
			'Rotates the view to look at, in priority order:\n' +
			' 1. The selected object, if any\n' +
			' 2. The sketch being edited',
			'./resources/lookatselectedorsketch',
			look_at_sketch_or_selected_handler)

	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutListActivateContainingOrComponentCommand',
			'Activate (containing) Component',
			'Activates the selected component. If no component is selected, '
			+ 'the component directly containing the selected object is activated.',
			'./resources/activate',
			activate_containing_component_handler)

	# For some reason, repeat captured using the tracking only works when clicking,
	# not with a keyboard shortcut.
	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutBuiltinRepeatCommand',
			'Repeat Last Command',
			'',
			'./resources/repeat',
			repeat_command_handler)
	
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutBuiltinAlignView',
			'Align The Camera',
			'',
			'./resources/repeat',
			alignViewHandler)

	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutBuiltinChangeView',
			'Change the view axis',
			'',
			'./resources/activate',
			changeViewAxis)

	create(builtin_dropdown_.controls,
			'thomasa88_anyShortcutBuiltinRotateCam',
			'Change the view axis',
			'',
			'./resources/repeat',
			createRotateCamera())

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	timeline_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('Timeline', './resources/timeline', 'thomasa88_anyShortcutBuiltinTimelineList')

	create(timeline_dropdown.controls,
			'thomasa88_anyShortcutListRollToBeginning',
			'Roll History Marker to Beginning',
			'',
			'./resources/timelinebeginning',
			create_roll_history_handler('moveToBeginning'))

	create(timeline_dropdown.controls,
			'thomasa88_anyShortcutListRollBack',
			'Roll History Marker Back',
			'',
			'./resources/timelineback',
			create_roll_history_handler('moveToPreviousStep'))
	
	create(timeline_dropdown.controls,
			'thomasa88_anyShortcutListRollForward',
			'Roll History Marker Forward',
			'',
			'./resources/timelineforward',
			create_roll_history_handler('movetoNextStep'))

	create(timeline_dropdown.controls,
			'thomasa88_anyShortcutListRollToEnd',
			'Roll History Marker to End',
			'',
			'./resources/timelineend',
			create_roll_history_handler('moveToEnd'))

	create(timeline_dropdown.controls,
			'thomasa88_anyShortcutListHistoryPlay',
			'Play History from Current Position',
			'',
			'./resources/timelineplay',
			create_roll_history_handler('play'))

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	view_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('View Orientation', './resources/viewfront', 'thomasa88_anyShortcutBuiltinViewList')
	for view in ['Front', 'Back', 'Top', 'Bottom', 'Left', 'Right']:
		create(view_dropdown.controls,
			'thomasa88_anyShortcutBuiltinView' + view,
			'View ' + view, '',
			'./resources/view' + view.lower(),
			create_view_orientation_handler(view))
		
	view_corner_dropdown:adsk.core.DropDownControl = builtin_dropdown_.controls.addDropDown('View Corner', './resources/viewisotopright', 'thomasa88_anyShortcutBuiltinCornerViewList')
	for view in ['IsoTopRight', 'IsoTopLeft','IsoBottomRight', 'IsoBottomLeft' ]:
		create(view_corner_dropdown.controls,
			'thomasa88_anyShortcutBuiltinCornerViewList' + view,
			'View ' + view.strip('Iso'), '',
			'./resources/view' + view.lower(),
			create_view_orientation_handler(view))

