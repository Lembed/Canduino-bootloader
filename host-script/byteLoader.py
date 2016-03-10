#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from sys import exit
#import time
#import math
from can import CanMsg
from enum import Enum
from time import sleep


if __name__ == "__main__":
	print( 'please run \'main.py\' instead' )
	exit( 0 )


states = Enum(
	'states',
	'INIT \
	REQ_IDENT \
	WAIT_IDENT_RESP \
	SET_ADDR \
	SET_ADDR_RESP \
	SEND_DATA \
	SEND_DATA_RESP \
	SEND_START_APP \
	GET_START_APP_RESP \
	ERROR \
	EXIT'
)

resp = Enum(
	'resp',
	'OK \
	END_OF_PAGE \
	NOT_END_OF_PAGE \
	ERROR'
)

class ByteLoader( ):
	def __init__( self, canBus ):
		# bus
		self.canBus = canBus
		self.canId = 0x133707FF

		# protocol
		self.state = states.INIT
		self.boardId = 0xFF
		self.msgNumber = 0
		self.fMsgCounter = 0
		self.pageSize = 0
		self.pageCount = 0

		# flashing
		self.flashPage = 0
		self.bufferPosition = 0
		self.fileData = []
		self.positionInFile = 0
	# end __init__()


	def importBinFile( self, fileName ):
		with open( fileName, 'rb' ) as f:
			self.fileData = bytes(f.read( -1 )) # read entire file
	# end importBinFile()



	def run( self ):
		# protocol description see
		# http://www.kreatives-chaos.com/artikel/can-bootloader
		while True:
			#sleep( 0.01 ) # seconds
			#input('enter to continue\n')


			if self.state == states.INIT:
				print( '' )
				print( '' )
				print( '' )
				print( 'state[INIT]' )
				self.msgNumber = 0
				self.fMsgCounter = 0
				print( '    data: msgNum =', self.msgNumber )
				print( '    data: fMsgNum =', self.fMsgCounter )
				print( '' )

				self.state = states.REQ_IDENT
				continue
			# end STATE INIT


			elif self.state == states.REQ_IDENT:
				print( 'state[REQ_IDENT]' )

				ok = self.__requestIdentify( )
				if ok is False:
					print( 'ERROR: cannot send identification request' )
					return 1

				print( '' )
				self.state = states.WAIT_IDENT_RESP
				continue
			# end STATE REQUEST IDENTIFICATION


			if self.state == states.WAIT_IDENT_RESP:
				print( 'state[WAIT_IDENT_RESP]' )

				ok = self.__getRequestIdentifyResponse( )
				if ok is False:
					print('ERROR: no identification response' )
					self.state = states.INIT
					continue
					#return 2

				# waiting here might take a while.
				# The device might not be powered already
				print( '' )
				self.state = states.SET_ADDR
				continue
			# end STATE GET IDENT RESPONSE

			if self.state == states.SET_ADDR:
				print ( 'state[SET_ADDR]' )

				ok = self.__setAddr( )
				if not ok:
					print( 'ERROR: cannot set address' )
					return 3


				print( '' )
				self.state = states.SET_ADDR_RESP
				continue
			# end STATE SET ADDRESS


			if self.state == states.SET_ADDR_RESP:
				print( 'state[SET_ADDR_RESP]' )

				ok = self.__getSetAddrResponse( )
				if not ok:
					print( 'ERROR: could not set address' )
					return 4

				print( '' )
				self.state = states.SEND_DATA
				continue
			# end STATE SET ADDRESS RESPONSE


			if self.state == states.SEND_DATA:
				print( 'state[SEND_DATA]' )

				ok = self.__sendPayloadData( )
				if( ok == resp.ERROR ):
					print( 'ERROR: could not send data' )
					return 5

				print( '' )
				if ( ok == resp.END_OF_PAGE ):
					self.state = states.SEND_DATA_RESP # ask for correctness of page
				else:
					self.state = states.SEND_DATA # send next 4 bytes
				continue
			# end STATE SEND DATA


			if self.state == states.SEND_DATA_RESP:
				print( 'state[SEND_DATA_RESP]' )

				ok = self.__getDataResponse( )
				if not ok:
					print( 'ERROR: sent data was not ok' )
					return 6

				print( '' )
				# send next 4 bytes on next page
				# page will be autoincremented by bootloader
				if( (len(self.fileData)-1) < self.positionInFile ):
					self.state = states.SEND_START_APP # done, now boot it
				else:
					self.state = states.SEND_DATA
				continue
			# end STATE GET SEND_DATA RESPONSE


			if self.state == states.SEND_START_APP:
				print( 'state[SEND_START_APP]' )

				ok = self.__sendStartApp( )
				if not ok:
					print( 'ERROR: sent data was not ok' )
					return 6

				print( '' )
				self.state = states.GET_START_APP_RESP
				continue
			# end STATE SEND START_APP MESSAGE

			if self.state == states.GET_START_APP_RESP:
				print( 'state[GET_START_APP_RESP]' )

				ok = self.__getStartAppResp( )
				if not ok:
					print( 'ERROR: sent data was not ok' )
					return 6

				print( '' )
				return 0
				continue
			# end STATE GET START_APP RESPONSE
			

			if self.state == states.EXIT:
				print( 'state[EXIT]' )
				return 0 # all was well
			# end STATE EXIT


			else:
				self.state = states.EXIT
			# end STATE UNKNOWN
		# end mainLoop
	# end run()



	def __receiveMsg( self ):
		retryCount = 0
		while True:
			rxMsg = self.canBus.getMsgNonBlocking( )

# !!!!!
# TODO: This needs a stable way to talk to bootloader on a high traffic bus
# !!!!!

			if rxMsg == None:
				retryCount -= 1
				sleep( 0.1 )
				if retryCount < 0:
					return False
				continue # TODO: timeout!

			if rxMsg == False:
				return False # something went wrong

			if rxMsg.id != self.canId -1:
				continue # not a bootloader message

			if self.boardId != rxMsg.data[0]:
				print( '    ERROR: boardId does not match' )
				print( '    Expected: 0x%02x, Got: 0x%02x' % (self.boardId, rxMsg.data[0]) )
				return False

			retType = rxMsg.data[1] >> 6
			retCmd = rxMsg.data[1] & 0x3F
			msgCnt = rxMsg.data[2]
			sob = rxMsg.data[3] >> 7
			fMsgCnt = rxMsg.data[3] & 0x7F

			print( '    data: boardId = 0x%02x' % rxMsg.data[0] )
			print( '    data: msgType=0x%02x, Command=0x%02x' % (retType, retCmd) )
			print( '    data: MsgCount =', msgCnt )
			print( '    data: SoB=%d, FMsgCount=%d' % (sob, fMsgCnt))

			if retType == 0x01:
				return rxMsg
			elif( retType == 0x03):
				print( '    ERROR: bootloader expected a different messageNumber' )
				print( '    It should have been: %d instead of %d' % (msgCnt, self.msgNumber) )
			else:
				print( '    ERROR: response type(0x%02x) indicates problem' % retType)
				return False
		# end while True
	# end __receiveMsg()




	def __requestIdentify( self ):
		txMsg = CanMsg( self.canBus, self.canId, True )
		print( '    > sending: Request to get Identification' )
		data = bytearray( )
		data.append( self.boardId ) # Board-ID
		data.append( 0x01 ) # Type = Request, Command = Identify
		data.append( self.msgNumber ) # iterates to spot missing messages
		data.append( 0x80 ) # SOB = 1, Following Msg Count = 0
		txMsg.setData( data )

		print( '    data: boardId = 0x%02x' % self.boardId )
		print( '    data: msgType = 0x%02x' % (0x00|0x02) )
		print( '    data: msgNum =', self.msgNumber )
		print( '    data: SOB=%d, fMsgCount=%d' % (1, 0) )

		self.msgNumber = self.msgNumber + 1

		ok = txMsg.send( )
		if ok == False:
			print( 'ERROR: Cannot send msg' )
			return False
		else:
			return True
	# end __requestIdentify()



	def __getRequestIdentifyResponse( self ):
		print( '    > waiting for: Identification response' )

		rxMsg = self.__receiveMsg( )

		if rxMsg == False:
			return False

		if rxMsg.data[5] == 0:
			self.pageSize = 32 # byte
		elif rxMsg.data[5] == 1:
			self.pageSize = 64 # byte
		elif rxMsg.data[5] == 2:
			self.pageSize = 128 # byte
		elif rxMsg.data[5] == 3:
			self.pageSize = 256 # byte
		else:
			self.pageSize = 0 # invalid

		self.pageCount = (rxMsg.data[6] << 8) + rxMsg.data[7]
		print( '    data: pageSize =', self.pageSize )
		print( '    data: rwwPageCount =', self.pageCount )

		return True
	# end __getRequestIdentifyResponse()


	def __setAddr( self ):
		txMsg = CanMsg( self.canBus, self.canId, True )
		print( '    > sending: Request SET ADDR command' )
		data = bytearray( )
		data.append( self.boardId ) # Board-ID
		data.append( 0x00|0x02 ) # Type = Request, Command = Set Address
		data.append( self.msgNumber ) # iterates to spot missing messages
		data.append( 0x80 ) # SOB = 1, Following Msg Count = 0

		data.append( 0x00 ) # start at the 1st flash page
		data.append( 0x00 )

		data.append( 0x00 ) # beginning of the page
		data.append( 0x00 )
		txMsg.setData( data )

		print( '    data: boardId = 0x%02x' % self.boardId )
		print( '    data: msgType = 0x%02x' % (0x00|0x02) )
		print( '    data: msgNum =', self.msgNumber )
		print( '    data: SOB=%d, fMsgCount=%d' % (1, 0) )
		print( '    data: flashPage =', self.flashPage )
		print( '    data: pageBufferPosition =', self.bufferPosition )

		self.msgNumber = self.msgNumber + 1

		ok = txMsg.send( )
		if ok == False:
			print( 'ERROR: Cannot send msg' )
			return False
		else:
			return True
	# end __setAddr()



	def __getSetAddrResponse( self ):
		print( '    > receiving: Response to SetAddr' )

		rxMsg = self.__receiveMsg( )

		if rxMsg == False:
			return False
		else:
			return True
	# end __getSetAddrResponse()


	def __sendPayloadData( self ):
		print( '    > sending: payload data for flashing' )
		txMsg = CanMsg( self.canBus, self.canId, True )

		if( self.fMsgCounter == 0 ):
			self.fMsgCounter = int(self.pageSize/4)
			sob = 0x80
		else:
			sob = 0x00
		self.fMsgCounter = self.fMsgCounter -1
		
		data = bytearray( )
		data.append( self.boardId ) # Board-ID
		data.append( (0x00|0x03) ) # Type = Request, Command = DATA
		data.append( self.msgNumber ) # iterates to spot missing messages
		data.append( (sob|self.fMsgCounter ) )


		if( (len(self.fileData)-1) < self.positionInFile ):
			data.append( 0xFF )
		else:
			data.append( self.fileData[self.positionInFile] )
			self.positionInFile += 1

		if( (len(self.fileData)-1) < self.positionInFile ):
			data.append( 0xFF )
		else:
			data.append( self.fileData[self.positionInFile] )
			self.positionInFile += 1

		if( (len(self.fileData)-1) < self.positionInFile ):
			data.append( 0xFF )
		else:
			data.append( self.fileData[self.positionInFile] )
			self.positionInFile += 1

		if( (len(self.fileData)-1) < self.positionInFile ):
			data.append( 0xFF )
		else:
			data.append( self.fileData[self.positionInFile] )
			self.positionInFile += 1

		txMsg.setData( data )

		print( '    data: boardId = 0x%02x' % self.boardId )
		print( '    data: msgType = 0x%02x' % (0x00|0x03) )
		print( '    data: msgNum =', self.msgNumber )
		print( '    data: SOB=%d, fMsgCount=%d' % ((sob>>7), self.fMsgCounter ) )
		print( '    data: [0x%02x][0x%02x][0x%02x][0x%02x]' % (data[4], data[5], data[6], data[7]) )
		print( '    data: dataLeft =', len(self.fileData) - self.positionInFile )

		#self.positionInFile = self.positionInFile +4
		self.msgNumber = self.msgNumber +1

		# manually make the counter wrap
		if self.msgNumber > 255:
			self.msgNumber = 0

		# TODO: check where to go next. In case of counte=0 check for response


		ok = txMsg.send( )
		if( ok == True ):
			if( self.fMsgCounter == 0 ):
				return resp.END_OF_PAGE
			else:
				return resp.NOT_END_OF_PAGE
		else:
			print( 'ERROR: Cannot send msg' )
			return resp.ERROR
	# __sendPayloadData()



	def __getDataResponse( self ):
		print( '    > receiving: Response to Data' )

		rxMsg = self.__receiveMsg( )


		if rxMsg == False:
			return False
		else:
			return True
	# end __getDataResponse()



	def __sendStartApp( self ):
		print( '    > sending: command to start application' )

		txMsg = CanMsg( self.canBus, self.canId, True )

		sob = 0x80
		self.fMsgCounter = 0
		
		data = bytearray( )
		data.append( self.boardId ) # Board-ID
		data.append( (0x00|0x04) ) # Type = Request, Command = START_APP
		data.append( self.msgNumber ) # iterates to spot missing messages
		data.append( (sob|self.fMsgCounter ) )

		txMsg.setData( data )

		ok = txMsg.send( )
		if( ok == True ):
			return True
		else:
			print( 'ERROR: Cannot send msg' )
			return resp.ERROR
	# end __sendStartApp()



	def __getStartAppResp( self ):
		print( '    > receiving: Response to Data' )

		rxMsg = self.__receiveMsg( )

		if rxMsg == False:
			return False
		else:
			return True
	# end __getStartAppResp()
