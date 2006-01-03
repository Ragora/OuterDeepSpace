#
#  Copyright 2001 - 2006 Ludek Smid [http://www.ospace.net/]
#
#  This file is part of IGE - Outer Space.
#
#  IGE - Outer Space is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  IGE - Outer Space is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with IGE - Outer Space; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

from pygameui.Widget import Widget, registerWidget
import pygameui as ui
from pygameui.Fonts import *
from ige.ospace.Const import *
from ige.ospace import Rules, Utils
import pygame, pygame.draw, pygame.key
from pygame.locals import *
from dialog.ShowBuoyDlg import ShowBuoyDlg
import gdata, client, log, res, math, string
from osci.dialog.SearchDlg import SearchDlg

buoyColors = [(0xff, 0xff, 0x00), (0x00, 0xff, 0xff), (0xff, 0x00, 0xff)]
MAX_BOUY_DISPLAY_LEN = 30

class StarMapWidget(Widget):

	MAP_SCANNER1 = 1
	MAP_SCANNER2 = 2
	MAP_SYSTEMS = 3
	MAP_PLANETS = 4
	MAP_FLEETS = 5
	MAP_FORDERS = 6
	MAP_OTHERS = 7
	MAP_FREDIRECTS = 8

	def __init__(self, parent, **kwargs):
		Widget.__init__(self, parent)
		self.searchDlg = SearchDlg(self.app)
		self.searchDlg.mapWidget = self
		# data
		self.action = None
		# map
		self._mapSurf = None
		self._map = {
			self.MAP_SCANNER1: [],
			self.MAP_SCANNER2: [],
			self.MAP_SYSTEMS: [],
			self.MAP_PLANETS: [],
			self.MAP_FLEETS: [],
			self.MAP_FORDERS: [],
			self.MAP_OTHERS: [],
			self.MAP_FREDIRECTS: [],
		}
		self._popupInfo = {}
		self._fleetRanges = {}
		self._fleetTarget = {}
		self._actAreas = {}
		self._actBuoyAreas = {}
		self.currX = 0.0
		self.currY = 0.0
		self.scale = 35.0
		self.activeObjID = OID_NONE
		self.activeObjIDs = []
		self.pressedObjIDs = []
		self._newCurrXY = 0
		self.activePos = (0, 0)
		self.repaintMap = 1
		self.setPosition = 1
		self.showScanners = 1
		self.showSystems = 1
		self.showPlanets = 1
		self.showFleets = 1
		self.showGrid = 1
		self.showRedirects = 1
		self.showPirateAreas = True
		self.highlightPos = None
		self.alwaysShowRangeFor = None
		self.showBuoyDlg = ShowBuoyDlg(self.app)
		# flags
		self.processKWArguments(kwargs)
		parent.registerWidget(self)
		# popup menu
		self.popup = ui.Menu(self.app, title = _("Select object"))
		self.popup.subscribeAction("*", self)

	def precompute(self):
		# clear active areas for buoy texts
		self._actBuoyAreas = {}
		player_highlight = -1
		if gdata.config.game.highlight != None:
			player_highlight = gdata.config.game.highlight
		self._map = {
			self.MAP_SCANNER1: [],
			self.MAP_SCANNER2: [],
			self.MAP_SYSTEMS: [],
			self.MAP_PLANETS: [],
			self.MAP_FLEETS: [],
			self.MAP_FORDERS: [],
			self.MAP_OTHERS: [],
			self.MAP_FREDIRECTS: [],
		}
		self._popupInfo = {}
		self._fleetRanges = {}
		# find all pirate planets
		pirates = {}
		log.debug("Checking pirate planets")
		for objID in client.db.keys():
			if objID < OID_FREESTART:
				continue
			obj = client.get(objID, noUpdate = 1)
			if not hasattr(obj, "type"):
				continue
			if obj.type == T_PLANET and hasattr(obj, "x"):
				ownerID = getattr(obj, 'owner', OID_NONE)
				if ownerID == OID_NONE:
					continue
				owner = client.get(ownerID, noUpdate = 1)
				if hasattr(owner, "type") and owner.type == T_PIRPLAYER:
					pirates[obj.x, obj.y] = None
		# process objects
		fleetOrbit = {}
		anyX = 0.0
		anyY = 0.0
		player = client.getPlayer()
		for objID in client.db.keys():
			if objID < OID_FREESTART:
				continue
			obj = client.get(objID, noUpdate = 1)
			if not hasattr(obj, "type"):
				continue
			try:
				if obj.type == T_PLAYER:
					continue
				if hasattr(obj, "x"):
					anyX = obj.x
				if hasattr(obj, "y"):
					anyY = obj.y
			except AttributeError, e:
				log.warning('StarMapWidget', 'Cannot render objID = %d' % objID)
				continue
			if obj.type == T_SYSTEM:
				player = client.getPlayer()
				img = res.getSmallStarImg(obj.starClass[1]) # TODO correct me
				icons = []
				name = getattr(obj, 'name', None)
				# TODO compute real relationship
				#rel = REL_UNDEF
				refuelMax = 0
				refuelInc = 0
				upgradeShip = 0
				repairShip = 0
				speedBoost = 0
				#owner2 = 0
				ownerID = OID_NONE
				if hasattr(obj, 'planets'):
					hasPirate = False
					for planetID in obj.planets:
						planet = client.get(planetID, noUpdate = 1)
						owner = getattr(planet, 'owner', OID_NONE)
						#rel = min(rel, client.getRelationTo(owner))
						if int(owner) != 0:
								ownerID = owner
				#		if int(player_highlight) == int(owner):
				#			owner2 = 1
						if hasattr(planet, "plStratRes") and planet.plStratRes != SR_NONE:
							icons.append(res.icons["sr_%d" % planet.plStratRes])
						if hasattr(planet, "refuelMax"):
							refuelMax = max(refuelMax, planet.refuelMax)
							refuelInc = max(refuelInc, planet.refuelInc)
						if hasattr(planet, "repairShip"):
							upgradeShip += planet.upgradeShip
							repairShip += planet.repairShip
						if hasattr(planet, "fleetSpeedBoost"):
							speedBoost = max(speedBoost, planet.fleetSpeedBoost)
				# pirates
				dist = 10000
				for pirX, pirY in pirates:
					dist = min(dist, math.hypot(obj.x - pirX, obj.y - pirY))
				pirProb = Rules.pirateGainFamePropability(dist)
				if pirProb >= 1.0:
					icons.append(res.icons["pir_99"])
				elif pirProb > 0.0:
					icons.append(res.icons["pir_00"])
				# refuelling
				if refuelMax >= 87:
					icons.append(res.icons["fuel_99"])
				elif refuelMax >= 62:
					icons.append(res.icons["fuel_75"])
				elif refuelMax >= 37:
					icons.append(res.icons["fuel_50"])
				elif refuelMax >= 12:
					icons.append(res.icons["fuel_25"])
				# repair and upgrade
				if upgradeShip > 10 and repairShip > 0.02:
					icons.append(res.icons["rep_10"])
				elif upgradeShip > 0 and repairShip > 0:
					icons.append(res.icons["rep_1"])
				if hasattr(obj, "combatCounter") and obj.combatCounter > 0:
					icons.append(res.icons["combat"])
				if hasattr(player, "buoys") and obj.oid in player.buoys:
					icons.append(res.icons["buoy_%d" % player.buoys[obj.oid][1]])
				if hasattr(player, "alliedBuoys") and obj.oid in player.alliedBuoys and len(player.alliedBuoys[obj.oid]) > 0:
					buoyName = "buoy_%d" % player.alliedBuoys[obj.oid][0][1]
					if len(player.alliedBuoys[obj.oid]) > 1:
						buoyName = "%s_plus" % buoyName
					icons.append(res.icons[buoyName])
				# star gates
				if speedBoost > 1.0:
					icons.append(res.icons["sg_%02d" % round(speedBoost)])
				#if owner2 != 0:
				#	color = gdata.playerHighlightColor
				#else:
				#	color = res.getFFColorCode(rel)
				color = res.getPlayerColor(ownerID)
				self._map[self.MAP_SYSTEMS].append((obj.oid, obj.x, obj.y, name, img, color, icons))
				# pop up info
				info = []
				info.append(_('System: %s [ID: %d]') % (name or res.getUnknownName(), obj.oid))
				info.append(_('Coordinates: [%.2f, %.2f]') % (obj.x, obj.y))
				info.append(_('Scan pwr: %d') % obj.scanPwr)
				info.append(_('Star Class: %s') % obj.starClass[1:])
				info.append(_('Star Type: %s') % _(gdata.starTypes[obj.starClass[0]]))
				if refuelMax > 0:
					info.append(_("Refuel: %d %%/turn [%d %% max]") % (refuelInc, refuelMax))
				if repairShip > 0:
					info.append(_("Repair ratio: %d %%/turn") % (repairShip * 100))
				if upgradeShip > 0:
					info.append(_("Upgrade points: %d/turn") % upgradeShip)
				if speedBoost > 0:
					info.append(_("Fleet speed: +%d %%") % (speedBoost * 100))
				if pirProb > 0.0:
					info.append(_("Pirate get fame chance: %d %%") % (pirProb * 100))
				self._popupInfo[obj.oid] = info
			elif obj.type == T_PLANET:
				owner = getattr(obj, 'owner', OID_NONE)
				name = getattr(obj, 'name', None) or res.getUnknownName()
				if hasattr(obj, "plType") and obj.plType in ("A", "G"):
					color = gdata.sevColors[gdata.DISABLED]
				else:
					#if int(player_highlight) == int(owner):
					#	color = gdata.playerHighlightColor
					#else:
					#	color = res.getFFColorCode(client.getRelationTo(owner))
					# color = res.getNColorCode(owner,client.getRelationTo(owner))
					color = res.getPlayerColor(owner)
				self._map[self.MAP_PLANETS].append((obj.oid, obj.x, obj.y, obj.orbit, color))
				scannerPwr = getattr(obj, 'scannerPwr', 0)
				if scannerPwr:
					self._map[self.MAP_SCANNER1].append((obj.x, obj.y, scannerPwr / 10.0))
					self._map[self.MAP_SCANNER2].append((obj.x, obj.y, scannerPwr / 16.0))
				# pop up info
				info = []
				info.append(_('Planet: %s [ID: %d]') % (name, obj.oid))
				if hasattr(obj, 'scanPwr'):	info.append(_('Scan pwr: %d') % obj.scanPwr)
				elif hasattr(obj, 'scannerPwr'): info.append(_('Scanner pwr: %d') % obj.scannerPwr)
				plType = gdata.planetTypes[getattr(obj, 'plType', None)]
				info.append(_('Type: %s') % _(plType))
				if hasattr(obj, 'plBio'): info.append(_('Environment: %d') % obj.plBio)
				if hasattr(obj, 'plMin'): info.append(_('Minerals: %d') % obj.plMin)
				if hasattr(obj, 'plEn'): info.append(_('Energy: %d') % obj.plEn)
				if hasattr(obj, "plStratRes") and obj.plStratRes != SR_NONE:
					info.append(_("Strat. resource: %s") % _(gdata.stratRes[obj.plStratRes]))
				if owner:
					player = client.get(owner)
					info.append(_('Owner: %s [ID: %s]') % (
						getattr(player, 'name', res.getUnknownName()),
						getattr(player, 'oid', '?')
					))
				self._popupInfo[obj.oid] = info
			elif obj.type == T_FLEET:
				owner = getattr(obj, 'owner', OID_NONE)
				name = getattr(obj, 'name', None) or res.getUnknownName()
				#if int(player_highlight) == int(owner):
				#	color = gdata.playerHighlightColor
				#else:
				#	color = res.getFFColorCode(client.getRelationTo(owner))
				# color = res.getNColorCode(owner,client.getRelationTo(owner))
				color = res.getPlayerColor(owner)
				scannerPwr = getattr(obj, 'scannerPwr', 0)
				if hasattr(obj, "scannerOn") and not obj.scannerOn:
					scannerPwr = 0
				if scannerPwr:
					self._map[self.MAP_SCANNER1].append((obj.x, obj.y, scannerPwr / 10.0))
					self._map[self.MAP_SCANNER2].append((obj.x, obj.y, scannerPwr / 16.0))
				orbit = -1
				if obj.orbiting != OID_NONE:
					orbit = fleetOrbit.get(obj.orbiting, 0)
					fleetOrbit[obj.orbiting] = orbit + 1
				eta = getattr(obj, 'eta', 0)
				self._map[self.MAP_FLEETS].append((obj.oid, obj.x, obj.y, obj.oldX, obj.oldY, orbit, res.formatTime(eta), color,
					obj.signature / 25, getattr(obj, "isMilitary", 0)))
				# pop up info
				info = []
				info.append(_('Fleet: %s [ID: %d]') % (name, obj.oid))
				if hasattr(obj, 'scanPwr'):	info.append(_('Scan pwr: %d') % obj.scanPwr)
				if hasattr(obj, 'scannerPwr'):	info.append(_('Scanner pwr: %d') % obj.scannerPwr)
				info.append(_('Coordinates: [%.2f, %.2f]') % (obj.x, obj.y))
				info.append(_('Signature: %d') % obj.signature)
				if eta:
					info.append(_('ETA: %s') % res.formatTime(eta))
				if owner:
					player = client.get(owner)
					info.append(_('Owner: %s [ID: %s]') % (
						getattr(player, 'name', res.getUnknownName()),
						getattr(player, 'oid', '?')
					))
				if hasattr(obj, 'storEn'):
					if obj.maxEn > 0: full = 100 * obj.storEn / obj.maxEn
					else: full = 0
					info.append(_('Tanks: %d / %d [%d %%]') % (obj.storEn, obj.maxEn, full))
					info.append(_('Support (fuel): %d/turn') % (obj.operEn))
					info.append(_('Support (const. pts): %d/turn') % (obj.operProd))
				if hasattr(obj, 'combatPwr'):
					info.append(_('Military power: %d') % obj.combatPwr)
				# ranges
				if hasattr(obj, 'storEn') and hasattr(obj, 'operEn'):
					turns = 100000
					if obj.operEn > 0: turns = obj.storEn / obj.operEn
					range = turns * obj.speed / Rules.turnsPerDay
					self._fleetRanges[obj.oid] = (obj.x, obj.y, range, (range  * 0.75) / 2, (range  * 0.5) / 2, obj.speed * 6 / Rules.turnsPerDay, turns)
					info.append("Operational time: %s" % res.formatTime(turns))
				if hasattr(obj, 'target') and obj.target != OID_NONE:
					target = client.get(obj.target, noUpdate=1)
					if hasattr(target, "x"):
						self._fleetTarget[obj.oid] = (obj.x, obj.y, target.x, target.y)
					info.append(_('Target: %s') % getattr(target, "name", res.getUnknownName()))
				if hasattr(obj, 'ships'):
					info.append(_('Ships:'))
					number = {}
					for designID, hp, shield, exp in obj.ships:
						tech = client.getPlayer().shipDesigns[designID]
						level = Rules.shipExpToLevel.get(int(exp / tech.baseExp), Rules.shipDefLevel)
						if designID not in number:
							number[designID] = [0, 0, 0, 0, 0]
						number[designID][level - 1] += 1
					order = number.keys()
					order.sort()
					for designID in order:
						tech = client.getPlayer().shipDesigns[designID]
						levels = number[designID]
						info.append(_('  %d x %s   [%d, %d, %d, %d, %d]') % (
								levels[0] + levels[1] + levels[2] + levels[3] + levels[4],
								tech.name,
								levels[0], levels[1], levels[2], levels[3], levels[4],
							)
						)
				elif hasattr(obj, 'shipScan'):
					info.append(_('Ships:'))
					for name, shipClass, isMilitary in obj.shipScan:
						if isMilitary:
							sType = _("military")
						else:
							sType = _("civilian")
						info.append(_("  %d x %s [%s %s ship]") % (
							obj.shipScan[name, shipClass, isMilitary],
							name,
							_(gdata.shipClasses[shipClass]),
							sType
						))
				if hasattr(obj, 'actionIndex') and not Utils.isIdleFleet(obj):
					action, target, data = obj.actions[obj.actionIndex]
					if target != OID_NONE:
						targetName = getattr(client.get(target, noUpdate = 1), 'name', res.getUnknownName())
					else:
						targetName = ""
					info.append(_("Command: %s %s") % (
						gdata.fleetActions[action],
						targetName,
					))
				self._popupInfo[obj.oid] = info
				# orders
				if hasattr(obj, 'actions'):
					oldX = obj.x
					oldY = obj.y
					for action, target, aData in obj.actions[obj.actionIndex:]:
						if target:
							# TODO add action colors
							if action == FLACTION_REFUEL: color = (0x00, 0x90, 0x00)
							elif action == FLACTION_DEPLOY: color = (0x90, 0x90, 0x00)
							elif action == FLACTION_REDIRECT: color = (0x20, 0x20, 0x80)
							else: color = (0x90, 0x90, 0x90)
							trgt = client.get(target, noUpdate = 1)
							if hasattr(trgt, 'x'):
								self._map[self.MAP_FORDERS].append((oldX, oldY, trgt.x, trgt.y, color))
								oldX, oldY = trgt.x, trgt.y
			elif obj.type == T_ASTEROID:
				owner = getattr(obj, 'owner', OID_NONE)
				name = getattr(obj, 'name', None) or res.getUnknownName()
				color = (0xff, 0xff, 0xff)
				scannerPwr = getattr(obj, 'scannerPwr', 0)
				orbit = -1
				if obj.orbiting != OID_NONE:
					orbit = fleetOrbit.get(obj.orbiting, 0)
					fleetOrbit[obj.orbiting] = orbit + 1
				eta = getattr(obj, 'eta', 0)
				self._map[self.MAP_FLEETS].append((obj.oid, obj.x, obj.y, obj.oldX, obj.oldY, orbit, res.formatTime(eta), color,
					obj.signature / 25, 0))
				# pop up info
				info = []
				info.append(_('Asteroid: %s [ID: %d]') % (name, obj.oid))
				if hasattr(obj, 'scanPwr'):	info.append(_('Scan pwr: %d') % obj.scanPwr)
				info.append(_('Coordinates: [%.2f, %.2f]') % (obj.x, obj.y))
				info.append(_('Signature: %d') % obj.signature)
				if hasattr(obj, 'asDiameter'): info.append(_('Diameter: %d') % obj.asDiameter)
				if hasattr(obj, 'asHP'): info.append(_('HP: %d') % obj.asHP)
				if hasattr(obj, 'speed'): info.append(_('Speed: %.2f') % obj.speed)
				if eta:
					info.append(_('ETA: %s') % res.formatTime(eta))
				if owner:
					player = client.get(owner)
					info.append(_('Owner: %s [ID: %s]') % (
						getattr(player, 'name', res.getUnknownName()),
						getattr(player, 'oid', '?')
					))
				self._popupInfo[obj.oid] = info
			elif obj.type == T_GALAXY:
				pass
			elif obj.type == T_UNKNOWN:
				# pop up info
				info = []
				info.append(_('Unknown object [ID: %d]') % obj.oid)
				if hasattr(obj, 'scanPwr'):
					info.append(_('Scan pwr: %d') % obj.scanPwr)
				self._popupInfo[obj.oid] = info
			else:
				log.warning('StarMapWidget', 'Unknown object type %d' % obj.type)
		# redirections
		player = client.getPlayer()
		for sourceID in player.shipRedirections:
			targetID = player.shipRedirections[sourceID]
			source = client.get(sourceID, noUpdate = 1)
			target = client.get(targetID, noUpdate = 1)
			if hasattr(source, "x") and hasattr(target, "y"):
				self._map[self.MAP_FREDIRECTS].append((source.x, source.y, target.x, target.y))
		# set position (typically on first show)
		if self.setPosition:
			self.setPosition = 0
			self.currX = anyX
			self.currY = anyY
		# self dirty flag
		self.repaintMap = 1

	def draw(self, surface):
		if not self._mapSurf:
			self._mapSurf = pygame.Surface(self.rect.size, SWSURFACE | SRCALPHA, surface)
			# workaround for FILLED CIRCLE CLIP BUG - TODO remove
			clip = self._mapSurf.get_clip()
			clip.left += 1
			clip.top += 1
			clip.width -= 2
			clip.height -= 2
			self._mapSurf.set_clip(clip)
			#
			self.repaintMap = 1
		if self.repaintMap:
			self._actAreas = {}
			mapSurface = self._mapSurf
			# redraw map
			mapSurface.fill((0x00, 0x00, 0x00))
			# coordinates
			centerX, centerY = mapSurface.get_rect().center
			maxY = mapSurface.get_rect().height
			currX = self.currX
			currY = self.currY
			scale = self.scale
			# clipping (TODO better one)
			clip = mapSurface.get_clip()
			# scanners
			# scanner ranges
			if self.showScanners:
				for x, y, range in self._map[self.MAP_SCANNER1]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					pygame.draw.circle(mapSurface, (0x00, 0x00, 0x60), (sx, sy), int(range * scale + 2), 0)
				for x, y, range in self._map[self.MAP_SCANNER1]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					pygame.draw.circle(mapSurface, (0x00, 0x00, 0x30), (sx, sy), int(range * scale), 0)
				for x, y, range in self._map[self.MAP_SCANNER2]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					pygame.draw.circle(mapSurface, (0x00, 0x00, 0x40), (sx, sy), int(range * scale), 0)
			# pirate area
			if self.showPirateAreas:
				pass # TODO
			# grid
			if self.showGrid:
				self.drawGrid()
			# redirections
			if self.showRedirects:
				for sx, sy, tx, ty in self._map[self.MAP_FREDIRECTS]:
					sx = int((sx - currX) * scale) + centerX
					sy = maxY - (int((sy - currY) * scale) + centerY)
					tx = int((tx - currX) * scale) + centerX
					ty = maxY - (int((ty - currY) * scale) + centerY)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx, sy), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx + 2, sy), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx - 2, sy), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx, sy + 2), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx, sy - 2), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx + 1, sy), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx - 1, sy), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx, sy + 1), (tx, ty), 1)
					pygame.draw.line(mapSurface, (0x20, 0x20, 0x80), (sx, sy - 1), (tx, ty), 1)
					# pygame.draw.line(mapSurface, (0x00, 0x00, 0x80), (sx, sy), ((sx + tx) / 2, (sy + ty) / 2), 3)
			# stars
			if self.showSystems:
				if scale >= 30:
					for objID, x, y, name, img, color, icons in self._map[self.MAP_SYSTEMS]:
						sx = int((x - currX) * scale) + centerX
						sy = maxY - (int((y - currY) * scale) + centerY)
						w, h = img.get_size()
						x = sx - w / 2
						y = sy - h / 2
						mapSurface.blit(img, (x, y))
						# images are now smaller - TODO fix images of stars
						w = 22
						h = 22
						if name:
							img = renderText('small', name, 1, color)
							mapSurface.blit(img, (sx - img.get_width() / 2, sy + h / 2))
							buoy = self.getBuoy(objID)
							if buoy != None:
								lines = buoy[0].split("\n")
								nSy = sy + h / 2 + img.get_height()
								maxW = 0
								hh = 0
								for line in lines:
									if len(line) == 0:
										break
									if len(line) > MAX_BOUY_DISPLAY_LEN:
										line = u"%s..." % line[:MAX_BOUY_DISPLAY_LEN]
									img = renderText('small', line, 1, buoyColors[buoy[1] - 1])
									maxW = max(img.get_width(), maxW)
									mapSurface.blit(img, (sx - img.get_width() / 2, nSy + hh))
									hh += img.get_height()
								if maxW > 0:
									actRect = Rect(sx - maxW / 2, nSy, maxW, hh)
									actRect.move_ip(self.rect.left, self.rect.top)
									self._actBuoyAreas[objID] = actRect
						for icon in icons:
							mapSurface.blit(icon, (x, y))
							x += icon.get_width() + 1
						# active rectangle
						actRect = Rect(sx - w / 2, sy - h / 2, w, h)
						actRect.move_ip(self.rect.left, self.rect.top)
						self._actAreas[objID] = actRect
				else:
					for objID, x, y, name, img, color, icons in self._map[self.MAP_SYSTEMS]:
						sx = int((x - currX) * scale) + centerX
						sy = maxY - (int((y - currY) * scale) + centerY)
						pygame.draw.circle(mapSurface, color, (sx, sy), 5, 1)
						pygame.draw.circle(mapSurface, color, (sx, sy), 4, 0)
						if name and scale > 15:
							img = renderText('small', name, 1, color)
							mapSurface.blit(img, (sx - img.get_width() / 2, sy + 6 / 2))
							buoy = self.getBuoy(objID)
							if buoy != None:
								lines = buoy[0].split("\n")
								nSy = sy + 6 / 2 + img.get_height()
								maxW = 0
								hh = 0
								for line in lines:
									if len(line) == 0:
										break
									img = renderText('small', line, 1, buoyColors[buoy[1] - 1])
									maxW = max(img.get_width(), maxW)
									mapSurface.blit(img, (sx - img.get_width() / 2, nSy + hh))
									hh += img.get_height()
								if maxW > 0:
									actRect = Rect(sx - maxW / 2, nSy, maxW, hh)
									actRect.move_ip(self.rect.left, self.rect.top)
									self._actBuoyAreas[objID] = actRect
						# active rectangle
						actRect = Rect(sx - 6 / 2, sy - 6 / 2, 6, 6)
						actRect.move_ip(self.rect.left, self.rect.top)
						self._actAreas[objID] = actRect
			# planets
			if self.showPlanets and scale >= 30:
				for objID, x, y, orbit, color in self._map[self.MAP_PLANETS]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					orbit -= 1
					actRect = Rect(sx + (orbit % 8) * 6 + 13, sy + 6 * (orbit / 8) - 6, 5, 5)
					mapSurface.fill(color, actRect)
					actRect.move_ip(self.rect.left, self.rect.top)
					self._actAreas[objID] = actRect
			elif self.showPlanets and scale > 20:
				for objID, x, y, orbit, color in self._map[self.MAP_PLANETS]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					orbit -= 1
					actRect = Rect(sx + (orbit % 8) * 3 + 7, sy - 3 * (orbit / 8) - 1, 2, 2)
					mapSurface.fill(color, actRect)
					actRect.move_ip(self.rect.left, self.rect.top)
					self._actAreas[objID] = actRect
			# fleets
			if self.showFleets:
				for x1, y1, x2, y2, color in self._map[self.MAP_FORDERS]:
					sx1 = int((x1 - currX) * scale) + centerX
					sy1 = maxY - (int((y1 - currY) * scale) + centerY)
					sx2 = int((x2 - currX) * scale) + centerX
					sy2 = maxY - (int((y2 - currY) * scale) + centerY)
					pygame.draw.line(mapSurface, color, (sx1, sy1), (sx2, sy2), 1)
				for objID, x, y, oldX, oldY, orbit, eta, color, size, military in self._map[self.MAP_FLEETS]:
					sx = int((x - currX) * scale) + centerX
					sy = maxY - (int((y - currY) * scale) + centerY)
					if orbit >= 0 and scale >= 30:
						actRect = Rect(sx + (orbit % 8) * 6 + 13, sy + 6 * (orbit / 8) + 6, 4, 4)
						# TODO this is a workaround - fix it when pygame gets fixed
						pygame.draw.polygon(mapSurface, color,
							(actRect.midleft, actRect.midtop, actRect.midright, actRect.midbottom), 1)
						pygame.draw.polygon(mapSurface, color,
							(actRect.midleft, actRect.midtop, actRect.midright, actRect.midbottom), 0)
						actRect.move_ip(self.rect.left, self.rect.top)
						self._actAreas[objID] = actRect
					elif orbit < 0:
						sox = int((oldX - currX) * scale) + centerX
						soy = maxY - (int((oldY - currY) * scale) + centerY)
						actRect = Rect(sx - 3, sy - 3, 6, 6)
						if military:
							mColor = color
						else:
							mColor = (0xff, 0xff, 0xff)
						pygame.draw.line(mapSurface, mColor, (sx, sy), (sox, soy), size + 1)
						# TODO rotate triangle
						pygame.draw.polygon(mapSurface, color,
							(actRect.midleft, actRect.midtop, actRect.midright, actRect.midbottom), 1)
						pygame.draw.polygon(mapSurface, color,
							(actRect.midleft, actRect.midtop, actRect.midright, actRect.midbottom), 0)
						if eta and scale > 15:
							img = renderText('small', eta, 1, color)
							mapSurface.blit(img, actRect.topright)
						actRect.move_ip(self.rect.left, self.rect.top)
						self._actAreas[objID] = actRect
			# clean up flag
			self.repaintMap = 0
		# blit cached map
		surface.blit(self._mapSurf, self.rect)
		# additional informations
		oldClip = surface.get_clip()
		surface.set_clip(self.rect)
		centerX, centerY = self._mapSurf.get_rect().center
		maxY = self._mapSurf.get_rect().height
		if self.highlightPos:
			sx = int((self.highlightPos[0] - self.currX) * self.scale) + centerX + self.rect.left
			sy = maxY - (int((self.highlightPos[1] - self.currY) * self.scale) + centerY) + self.rect.top
			pygame.draw.circle(surface, (0xff, 0xff, 0xff), (sx, sy), 13, 2)
		if self.alwaysShowRangeFor and self._fleetRanges.has_key(self.alwaysShowRangeFor):
			x, y, maxRange, operRange, halfRange, speed, turns = self._fleetRanges[self.alwaysShowRangeFor]
			sx = int((x - self.currX) * self.scale) + centerX + self.rect.left
			sy = maxY - (int((y - self.currY) * self.scale) + centerY) + self.rect.top
			rng = max(maxRange * self.scale, 0.2 * self.scale)
			if rng > 1:
				pygame.draw.circle(surface, (0xc0, 0x20, 0x20), (sx, sy), int(rng), 1)
			rng = operRange * self.scale
			if rng > 1:
				pygame.draw.circle(surface, (0x20, 0x80, 0x20), (sx, sy), int(rng), 1)
			rng = halfRange * self.scale
			if rng > 1:
				pygame.draw.circle(surface, (0x20, 0x20, 0x80), (sx, sy), int(rng), 1)
		# draw ranges
		for activeObjID in self.activeObjIDs:
			if activeObjID and activeObjID in self._fleetTarget:
				x, y, x1, y1 = self._fleetTarget[activeObjID]
				sx = int((x - self.currX) * self.scale) + centerX + self.rect.left
				sy = maxY - (int((y - self.currY) * self.scale) + centerY) + self.rect.top
				dx = int((x1 - self.currX) * self.scale) + centerX + self.rect.left
				dy = maxY - (int((y1 - self.currY) * self.scale) + centerY) + self.rect.top
				pygame.draw.line(surface, (0xff, 0xff, 0x00), (sx, sy), (dx, dy), 2)
			if activeObjID and activeObjID in self._fleetRanges:
				x, y, maxRange, operRange, halfRange, speed, turns = self._fleetRanges[activeObjID]
				sx = int((x - self.currX) * self.scale) + centerX + self.rect.left
				sy = maxY - (int((y - self.currY) * self.scale) + centerY) + self.rect.top
				if pygame.key.get_mods() & KMOD_SHIFT:
					for i in xrange(1, turns / 6):
						rng = int(i * speed * self.scale)
						if rng > 1:
							pygame.draw.circle(surface, (0x70, 0x70, 0x80), (sx, sy), rng, 1)
							textSrfc = renderText('small', res.formatTime(i * 6), 1, (0x70, 0x70, 0x80), (0x00, 0x00, 0x00))
							surface.blit(textSrfc, (sx - rng, sy - textSrfc.get_height() / 2))
							surface.blit(textSrfc, (sx + rng, sy - textSrfc.get_height() / 2))
							surface.blit(textSrfc, (sx - textSrfc.get_width() / 2, sy - rng))
							surface.blit(textSrfc, (sx - textSrfc.get_width() / 2, sy + rng - textSrfc.get_height()))
					rng = int(max(maxRange * self.scale, 0.2 * self.scale))
					if rng > 1:
						pygame.draw.circle(surface, (0xc0, 0x20, 0x20), (sx, sy), rng, 1)
				else:
					rng = int(max(maxRange * self.scale, 0.2 * self.scale))
					if rng > 1:
						pygame.draw.circle(surface, (0xc0, 0x20, 0x20), (sx, sy), rng, 1)
					rng = int(operRange * self.scale)
					if rng > 1:
						pygame.draw.circle(surface, (0x20, 0x80, 0x20), (sx, sy), rng, 1)
					rng = int(halfRange * self.scale)
					if rng > 1:
						pygame.draw.circle(surface, (0x20, 0x20, 0x80), (sx, sy), rng, 1)
		# draw popups
		moreIDs = len(self.activeObjIDs) > 1
		if not moreIDs:
			x, y = self.activePos
			x += 20
		else:
			x = self.rect.left + 2
			y = self.rect.top
		if not pygame.key.get_mods() & KMOD_SHIFT:
			for activeObjID in self.activeObjIDs:
				index = 0
				if self._popupInfo.has_key(activeObjID):
					# put pop up info on the screen
					info = self._popupInfo[activeObjID]
					# x1, y1 = self._actAreas[self.activeObjID].center
					fg = self.theme.themeForeground #(0x30, 0xe0, 0x30, 0xff)
					bg = self.theme.themeBackground #(0x20, 0x40, 0x20, 0x99)
					width = 0
					height = 0
					# pygame.draw.line(surface, fg, (x1, y1), (x, y), 1)
					for item in info:
						w, h = getTextSize('small', item)
						width = max(width, w)
						height += h
					if not moreIDs:
						if x + width >= self.rect.width:
							x -= width + 40
						if y + 1 + height >= self.rect.height:
							y -= height
					surface.fill(bg, (x, y, width + 2, height + 2))
					x += 1
					tmpY = y + 1
					for item in info:
						textSrfc = renderText('small', item, 1, fg)
						surface.blit(textSrfc, (x, tmpY))
						tmpY += textSrfc.get_height()
					x += width + 2
		# restore clipping
		surface.set_clip(oldClip)
		#
		return self.rect

	def getBuoy(self, objID):
		player = client.getPlayer()
		if hasattr(player, "buoys") and objID in player.buoys:
			lines = player.buoys[objID][0].split("\n")
			if len(lines) > 2:
				return (u"%s\n%s" % (lines[0], lines[1]), player.buoys[objID][1])
			else:
				return player.buoys[objID]
		else:
			if hasattr(player, "alliedBuoys") and objID in player.alliedBuoys:
				if len(player.alliedBuoys[objID]) > 0:
					lines = player.alliedBuoys[objID][0][0].split("\n")
					if len(lines) > 2:
						return (u"%s\n%s" % (lines[0], lines[1]), player.alliedBuoys[objID][0][1])
					else:
						return player.alliedBuoys[objID][0]
				else:
					return None
			else:
				return None

	def drawGrid(self):
		rect = self._mapSurf.get_rect()
		centerX, centerY = rect.center
		maxY = rect.height
		currX = self.currX
		currY = self.currY
		scale = self.scale
		left = int((int(currX) - currX) * scale) + centerX - int(rect.width / scale / 2) * scale
		x = left
		while x < left + rect.width + scale:
			value =  math.floor((x - centerX) / scale + currX)
			if value % 5 == 0:
				pygame.draw.line(self._mapSurf, (0x00, 0x00, 0x90),
					(x, rect.top), (x, rect.bottom), 1)
				textSrfc = renderText('small', int(value), 1, (0x70, 0x70, 0x80))
				self._mapSurf.blit(textSrfc, (x + 2, rect.height - textSrfc.get_height()))
			else:
				pygame.draw.line(self._mapSurf, (0x33, 0x33, 0x66),
					(x, rect.top), (x, rect.bottom), 1)
			x += scale
		top = int((int(currY) - currY) * scale) + centerY - int(rect.height / scale / 2) * scale
		y = top
		while y < top + rect.height + scale:
			yScrn = maxY - y
			value =  math.floor(((maxY - yScrn) - centerY) / scale + currY)
			if value % 5 == 0:
				pygame.draw.line(self._mapSurf, (0x00, 0x00, 0x90),
					(rect.left, yScrn), (rect.right, yScrn), 1)
				textSrfc = renderText('small', int(value), 1, (0x70, 0x70, 0x80))
				self._mapSurf.blit(textSrfc, (0, yScrn))
			else:
				pygame.draw.line(self._mapSurf, (0x33, 0x33, 0x66),
					(rect.left, yScrn), (rect.right, yScrn), 1)
			y += scale

	def processMB1Down(self, evt):
		# handle SHIFT click as MB3
		mods = pygame.key.get_mods()
		if mods & KMOD_SHIFT:
			return self.processMB3Down(evt)
		pos = evt.pos
		self.pressedObjIDs = []
		for objID in self._actAreas.keys():
			rect = self._actAreas[objID]
			if rect.collidepoint(pos):
				self.pressedObjIDs.append(objID)

		self.pressedBuoyObjIDs = []
		for objID in self._actBuoyAreas.keys():
			rect = self._actBuoyAreas[objID]
			if rect.collidepoint(pos):
				self.pressedBuoyObjIDs.append(objID)

		if self.pressedObjIDs or self.pressedBuoyObjIDs:
			return ui.NoEvent
		else:
			self.activeObjID = OID_NONE
			return ui.NoEvent

	def processMB1Up(self, evt):
		# handle SHIFT click as MB3
		mods = pygame.key.get_mods()
		if mods & KMOD_SHIFT:
			return self.processMB3Up(evt)
		pos = evt.pos
		objIDs = []
		for objID in self._actAreas.keys():
			rect = self._actAreas[objID]
			if rect.collidepoint(pos):
				objIDs.append(objID)

		bObjIDs = []
		for objID in self._actBuoyAreas.keys():
			rect = self._actBuoyAreas[objID]
			if rect.collidepoint(pos):
				bObjIDs.append(objID)

		if (objIDs or bObjIDs) and (self.pressedObjIDs == objIDs or self.pressedBuoyObjIDs == bObjIDs) and self.action:
			if len(objIDs) + len(bObjIDs) == 1:
				if len(objIDs) == 1:
					self.processAction(self.action, objIDs[0])
					self.pressedObjIDs = []
				else:
					self.showBuoyDlg.display(bObjIDs[0])
					self.pressedBuoyObjIDs = []
			else:
				# multiple objects -> post pop-up menu
				items = []
				for objID in objIDs:
					obj = client.get(objID)
					if obj.type == T_SYSTEM:
						name = getattr(obj, "name", None)
						name = _("System: %s [ID: %d]") % (name or res.getUnknownName(), obj.oid)
					elif obj.type == T_PLANET:
						name = getattr(obj, "name", None)
						name = _("Planet: %s [ID: %d]") % (name or res.getUnknownName(), obj.oid)
					elif obj.type == T_FLEET:
						name = getattr(obj, "name", None)
						name = _("Fleet: %s [ID: %d]") % (name or res.getUnknownName(), obj.oid)
					elif obj.type == T_ASTEROID:
						name = getattr(obj, "name", None)
						name = _("Asteroid: %s [ID: %d]") % (name or res.getUnknownName(), obj.oid)
					else:
						name = _("Unknown object [ID: %d]") % obj.oid
					item = ui.Item(name, action = "onObjectSelected", data = objID)
					items.append(item)

				for objID in bObjIDs:
					obj = client.get(objID)
					if obj.type == T_SYSTEM:
						name = getattr(obj, "name", None)
						name = _("Buoy on system: %s [ID: %d]") % (name or res.getUnknownName(), obj.oid)
					else:
						name = _("Buoy on unknown object [ID: %d]") % obj.oid

					item = ui.Item(name, action = "onBuoySelected", data = objID)
					items.append(item)

				self.popup.items = items
				self.popup.show()
			return ui.NoEvent
		else:
			self.activeObjID = OID_NONE
			return ui.NoEvent

	def onObjectSelected(self, widget, action, data):
		self.processAction(self.action, data)

	def onBuoySelected(self, widget, action, data):
		self.showBuoyDlg.display(data)

	def processMB3Down(self, evt):
		self._newCurrXY = 1
		return ui.NoEvent

	def processMB3Up(self, evt):
		if self._newCurrXY:
			x, y = evt.pos
			centerX, centerY = self._mapSurf.get_rect().center
			self.currX -= float(centerX - x) / self.scale
			self.currY += float(centerY - y) / self.scale
			self.repaintMap = 1
			self._newCurrXY = 0
		return ui.NoEvent

	def processMWUp(self, evt):
		self.scale += 5
		self.repaintMap = 1
		return ui.NoEvent

	def processMWDown(self, evt):
		if self.scale > 10:
			self.scale -= 5
			self.repaintMap = 1
		return ui.NoEvent

	def processMMotion(self, evt):
		pos = evt.pos
		self.activeObjID = OID_NONE
		self.activeObjIDs = []
		for objID in self._actAreas.keys():
			rect = self._actAreas[objID]
			if rect.collidepoint(pos):
				self.activeObjID = objID
				self.activeObjIDs.append(objID)
				self.activePos = pos
		return ui.NoEvent

	def processKeyDown(self, evt):
		if not evt.unicode:
			# force update
			self.scale += 1
			self.scale -= 1
			return ui.NoEvent
		if evt.unicode in u'+=':
			self.scale += 5
			self.repaintMap = 1
		elif evt.unicode == u'-':
			if self.scale > 10:
				self.scale -= 5
				self.repaintMap = 1
		# Ctrl+F
		elif evt.unicode == u'\x06' and pygame.key.get_mods() & KMOD_CTRL:
			self.searchDlg.display()
		elif evt.unicode == u' ':
			x, y = pygame.mouse.get_pos()
			centerX, centerY = self._mapSurf.get_rect().center
			self.currX -= float(centerX - x) / self.scale
			self.currY += float(centerY - y) / self.scale
			self.repaintMap = 1
			self._newCurrXY = 0
		else:
			# force update
			self.scale += 1
			self.scale -= 1
		return ui.NoEvent

	def setPos(self, x, y):
		self.currX = x
		self.currY = y
		self.repaintMap = 1
		# disable auto position setting
		self.setPosition = 0

registerWidget(StarMapWidget, 'starmapwidget')
