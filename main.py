#
#  SwitchBot Kicker v1.34
#       written by Tsuyoshi HASEGAWA 2025
#
import network
import usocket as socket
import struct
import ubinascii
import uasyncio
import utime
import gc
import aiohttp
import ujson
import select
from collections import OrderedDict
from microdot import Microdot
from machine import Pin

import usersettings as USER


LED = machine.Pin('LED', Pin.OUT)
def ledon():
    LED.high()

def ledoff():
    LED.low()


def OffsetUTCtime():
    utc_time = utime.localtime()
    ret = utime.mktime(utc_time) + USER.UTC_OFFSET
    return ret if ret>=0 else 0

def DatetimeString(nowtime):
    lt = utime.localtime(nowtime)
    wdnames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    return f'{lt[0]:04d}/{lt[1]:02d}/{lt[2]:02d} {wdnames[lt[6]]:s} {lt[3]:02d}:{lt[4]:02d}:{lt[5]:02d}'

logqueue = []
def loginit():
    for i in range(16):
        logqueue.append('')

def log(s,d=True):
    global logqueue
    if len(logqueue)>=16:
        logqueue.pop(0)
    logqueue.append(f'{DatetimeString(OffsetUTCtime())} | {s}')
    if d: print(s)

def logActive():
    if '| Worker Active' in logqueue[-1]:
        logqueue.pop()
    log('Worker Active', False)


def DispMACAddress():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()
    log(f'MAC address: {mac}')

def ConnectNetwork():
    network.hostname("swbotkicker")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(USER.NET_SSID, USER.NET_PASS)

    log('Connecting...')
    while not wlan.isconnected():
        utime.sleep(1)
        print('Connecting...')

    log(f'WiFi Connected. IP address: {wlan.ifconfig()[0]}')


def ResetRTC():
    SetRTC(utime.localtime(0))

def SetRTC(rtct):
    machine.RTC().datetime((rtct[0], rtct[1], rtct[2], rtct[6], rtct[3], rtct[4], rtct[5], 0))

def TimeFromNTP():
    NTP_DELTA = 2208988800
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(USER.NTP_HOST, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    s.sendto(NTP_QUERY, addr)
    try:
        msg = s.recv(48)
    except OSError:
        log('No responce from NTP server.')
        return 0
    finally:
        s.close()

    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA

def AdjustTime():
    ntp_time = TimeFromNTP()
    if ntp_time != 0:
        SetRTC(utime.localtime(ntp_time))
        log('Adjust RTC with NTP.')
        return OffsetUTCtime()
    else:
        log('Adjust RTC failure.')
        return 0

def DispBootReason():
    reset_cause = machine.reset_cause()
    if reset_cause == machine.PWRON_RESET:
        log('Boot cause Power-ON.')
    elif reset_cause == machine.WDT_RESET:
        log('Reboot cause WDT reset.')
    else:
        log('Reboot cause unknown reason.')


# (NAME,WEEKDAYS,HOUR,MINUTE,SECOND,YEAR,MONTH,DAY,SCENENAME,ACTIVE)
DataBase=[]
CnfFileName='SwBotKicker.cnf'
def SetupDataBase():
    global DataBase
    DataBase.clear()
    try:
        with open(CnfFileName, 'r', encoding='utf-8') as file:
            DataBase = eval(file.read())
        log('Configulation loaded.')
    except Exception as e:
        log('No Configulation')
        DataBase.clear()

def SaveDataBase():
    global DataBase
    with open(CnfFileName, 'w', encoding='utf-8') as file:
        print(f'{DataBase}', file=file)
    log('Configulation saved.')


SCENEDIC = OrderedDict([('(_initial_)','')])
DicFileName='SwBotKicker.dic'
def SetupSceneDic():
    global SCENEDIC
    try:
        with open(DicFileName, 'r', encoding='utf-8') as file:
            SCENEDIC = eval(file.read())
        log('Scene dictionary loaded.')
    except Exception as e:
        log('No scene dictionary')

def SaveSceneDic():
    global SCENEDIC
    with open(DicFileName, 'w', encoding='utf-8') as file:
        print(f'{SCENEDIC}', file=file)
    log('Scene dictionary saved.')


APIheaders = {
    "Authorization": "Bearer " + USER.SB_API_TOKEN,
    "Content-Type": "application/json"
}
async def RetrieveScenes():
    url = 'https://api.switch-bot.com/v1.0/scenes'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, json=None, headers=APIheaders) as response:
            jsontext = await response.text() if response.status==200 else ''
    return jsontext

async def ExecuteScene(SCENE_ID):
    if SCENE_ID=='':
        log(f'SceneID is empty.')
        return

    log(f'Execute scene {SCENE_ID}')
    url = f"https://api.switch-bot.com/v1.0/scenes/{SCENE_ID}/execute"
    ledon()
    gc.collect()
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=None, headers=APIheaders) as response:
            if response.status == 200:
                log(f'Scene {SCENE_ID} is executed successfully.')
            else:
                log(f'Failed to execute scene:{response.text}')
    ledoff()


# Interface variables between web server and worker
testtime = 0
testscene = ''
adjusttime = 0

# Share variable between web pages
parsed_scenes = None

async def web_server():

    TITLE = 'SwitchBot Kicker'
    HEADLINE = 'SwitchBot Kicker v1.34'

    WDPAT = (
        ((0,1,2,3,4,5,6),USER.DESC_TEXT_EVERYDAY),
        ((0,1,2,3,4),USER.DESC_TEXT_WEEKDAYS),
        ((0,1,2,3),USER.DESC_TEXT_MON2THU),
        ((0,),USER.DESC_TEXT_MONDAY),
        ((1,),USER.DESC_TEXT_TUESDAY),
        ((2,),USER.DESC_TEXT_WEDNESDAY),
        ((3,),USER.DESC_TEXT_THURSDAY),
        ((4,),USER.DESC_TEXT_FRIDAY),
        ((5,),USER.DESC_TEXT_SATURDAY),
        ((6,),USER.DESC_TEXT_SUNDAY),
        ((4,5,6),USER.DESC_TEXT_FRI2SUN),
        ((5,6),USER.DESC_TEXT_WEEKEND),
    )

    html_backhome = f'''
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>{TITLE}</title>
<style>body {{color: #ffffff; background-color: #000000;}}</style>
<meta http-equiv="refresh" content="0;url=/" />
</head><body></body></html>
'''
    html_transregist = f'''
<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>{TITLE}</title>
<style>body {{color: #ffffff; background-color: #000000;}}</style>
<meta http-equiv="refresh" content="0;url=/regist" />
</head><body></body></html>
'''
    html_headers = {'Content-Type': 'text/html'}

    app = Microdot()

    # Log display / select edit schedule
    @app.route('/')
    async def _index(request):
        gc.collect()
        LOGS=''
        for s in logqueue:
            LOGS += f' {s}\n'

        gc.collect()
        forms = f'''
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>{TITLE}</title><style> body {{color: #ffffff; background-color: #000000;}}
.form-container {{ display: flex; flex-direction: column; gap: 1px; }}
.form-row {{ display: flex; align-items: center; gap: 8px; }}
</style></head><body><h1>{HEADLINE}</h1>
<pre>Log updated: {DatetimeString(OffsetUTCtime())}</pre><p></p>
<pre>{LOGS}</pre><hr><div class="form-container">
'''
        for i in range(len(DataBase)):
            gc.collect()
            # (NAME,WEEKDAYS,HOUR,MINUTE,SECOND,YEAR,MONTH,DAY,SCENENAME,ACTIVE)
            n = DataBase[i]
            IDNO=i
            NAME=n[0]
            WKDY=n[1]
            HOUR=n[2]
            MINU=n[3]
            SECO=n[4]
            ACTV=' checked' if n[9] else '' 

            HD = f'{HOUR:02d}' if HOUR>=0 else '**'
            MD = f'{MINU:02d}' if MINU>=0 else '**'
            WKDN=''
            for D in WDPAT:
                if D[0]==WKDY:
                    WKDN=D[1]
                    break
            forms += f'''
<form action="/edit" method="post" class="form-row">
<input type="hidden" name="id" value="{IDNO}">
<button type="submit" name="action" value="change">{USER.DESC_BUTTON_CHANGE}</button>
<button type="submit" name="action" value="test">{USER.DESC_BUTTON_EXECTEST}</button>
<input type="checkbox"{ACTV} disabled>
{WKDN} {HD}:{MD}:{SECO:02d}　{NAME}
</form>
'''
        if len(DataBase)==0:
            forms += f'<label>{USER.DESC_TEXT_NOSCHEDULE}</label>'

        DISABLE = ' disabled' if '(_initial_)' in SCENEDIC.keys() else ''
        forms += f'''
</div><hr><form action="/edit" method="post" class="form-row">
<input type="hidden" name="id" value="-1">
<button type="submit" name="action" value="change"{DISABLE}>{USER.DESC_BUTTON_ADDSCHEDULE}</button>
<button type="submit" name="action" value="adjust">{USER.DESC_BUTTON_TIMEADJUST}</button>
<button type="submit" name="action" value="regist">{USER.DESC_BUTTON_SCENEREGIST}</button>
</form></body></html>
'''
        gc.collect()
        return forms, 200, html_headers


    # Edit schedule (and interface with worker)
    @app.route('/edit', methods=['POST'])
    async def _edit(request):
        global testtime
        global testscene
        global adjusttime

        gc.collect()
        action = request.form.get('action')
        if action =='test':
            i = int(request.form.get('id',-1))
            scenename = DataBase[i][8]
            testscene = SCENEDIC[scenename]
            testtime = OffsetUTCtime()+1
            log(f'Kick test scheduled: {testscene}')
            return html_backhome, 200, html_headers

        if action == 'adjust':
            adjusttime = OffsetUTCtime()+1
            log('Time adjust scheduled.')
            return html_backhome, 200, html_headers

        if action == 'regist':
            return html_transregist, 200, html_headers

        gc.collect()
        forms = f'''
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>{TITLE}</title>
<style> body {{color: #ffffff; background-color: #000000;}}
.form-container {{ display: flex; flex-direction: column; gap: 1px; }}
.form-row {{ display: flex; align-items: center; gap: 10px; }}
</style></head><body>
<h1>{HEADLINE}</h1>
<p>{USER.DESC_TEXT_SCHEDULESETTING}</p>
<div class="form-container">
'''
        i = int(request.form.get('id',-1))
        n = DataBase[i] if i>=0 else ('(noname)',(0,1,2,3,4,5,6),12,0,0,0,0,0,next(iter(SCENEDIC)),True)
        itsnew = i==-1
        IDNO=i
        # (NAME,WEEKDAYS,HOUR,MINUTE,SECOND,YEAR,MONTH,DAY,SCENENAME,ACTIVE)
        NAME=n[0]
        WKDY=n[1]
        HOUR=n[2]
        MINU=n[3]
        SECO=n[4]
        SNAM=n[8]
        ACTV=' checked' if n[9]==True else ''
        gc.collect()

        forms += f'''
<form action="/apply" method="post" class="form-row">
<input type="hidden" name="id" value="{IDNO}">
<input type="checkbox" name="active" value="1"{ACTV}>
<input type="text" name="name" value="{NAME}">
'''
        temp = '<select name="weekday">'
        for j in range(len(WDPAT)):
            sel = ' selected' if WDPAT[j][0]==WKDY else ''
            temp += f'<option value="{WDPAT[j][0]}"{sel}>{WDPAT[j][1]}</option>'
        temp += '</select>'
        forms += temp

        temp = '<select name="hour">'
        for j in range(-1,24):
            cap = f'{j}' if j>=0 else '**'
            sel = ' selected' if j==HOUR else ''
            temp += f'<option value="{j}"{sel}>{cap}</option>'
        temp += '</select>'
        forms += temp

        temp = '<select name="minute">'
        for j in range(-1,60):
            cap = f'{j:02d}' if j>=0 else '**'
            sel = ' selected' if j==MINU else ''
            temp += f'<option value="{j}"{sel}>{cap}</option>'
        temp += '</select>'
        forms += temp

        temp = '<select name="second">'
        for j in range(60):
            sel = ' selected' if j==SECO else ''
            temp += f'<option value="{j}"{sel}>{j:02d}</option>'
        temp += '</select>'
        forms += temp

        temp = '<select name="scenename">'
        for s in SCENEDIC.keys():
            sel = ' selected' if s==SNAM else ''
            temp += f'<option value="{s}"{sel}>{s}</option>'
        temp += '</select>'
        forms += temp

        del temp
        temp = None
        gc.collect()
        
        if itsnew:
            forms += f'''
<button type="submit" name="action" value="change">{USER.DESC_BUTTON_APPEND}</button>
<button type="submit" name="action" value="cancel">{USER.DESC_BUTTON_APPENDCANCEL}</button>
'''
        else:
            forms += f'''
<button type="submit" name="action" value="change">{USER.DESC_BUTTON_CHANGE}</button>
<button type="submit" name="action" value="cancel">{USER.DESC_BUTTON_CHANGECANCEL}</button>
<button type="submit" name="action" value="delete">{USER.DESC_BUTTON_DELETE}</button>
'''
        forms += '</form></div></body></html>'

        gc.collect()
        return forms, 200, html_headers

    # Apply edited schedule
    @app.route('/apply', methods=['POST'])
    async def _apply(request):
        action = request.form.get('action','cancel')
        id = int(request.form.get('id',-100))

        if action == 'cancel' or id==-100:
            return html_backhome, 200, html_headers

        if action == 'delete':
            if id >= 0:
                del DataBase[id]
                SaveDataBase()
            return html_backhome, 200, html_headers

        # (NAME,WEEKDAYS,HOUR,MINUTE,SECOND,YEAR,MONTH,DAY,SCENENAME,ACTIVE)
        if id == -1:
            DataBase.append(('(empty)',(-1,),0,0,0,0,0,0,'',True))
            id = len(DataBase)-1

        L = list(DataBase[id])
        L[0] = request.form.get('name','(noname)')
        L[1] = eval(request.form.get('weekday','(0,1,2,3,4,5,6)'))
        L[2] = int(request.form.get('hour',12))
        L[3] = int(request.form.get('minute',0))
        L[4] = int(request.form.get('second',0))
        L[8] = request.form.get('scenename','')
        L[9] = request.form.get('active','0')=='1'
        DataBase[id] = tuple(L)
        print(f'Update DataBase: {id} {DataBase[id]}')
        SaveDataBase()
        gc.collect()
        return html_backhome, 200, html_headers


    # Select Switchbot scenes to regist
    @app.route('/regist')
    async def _regist(request):
        global parsed_scenes
        if parsed_scenes==None:
            jsontext = await RetrieveScenes()
            if jsontext=='':
                log('Retrieve scenes failed.')
                return html_backhome, 200, html_headers
            parsed_json = ujson.loads(jsontext)
            parsed_scenes = {}
            for S in parsed_json['body']:
                parsed_scenes[S['sceneName']] = S['sceneId']
            del parsed_json

        forms = f'''
<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>{TITLE}</title>
<style> body {{color: #ffffff; background-color: #000000;}}
.form-container {{ display: flex; flex-direction: column; gap: 1px; }}
.form-row {{ display: flex; align-items: center; gap: 10px; }}
</style></head><body>
<h1>{HEADLINE}</h1>
<p>{USER.DESC_TEXT_REGISTSCENES}</p>
<form action="/regapply" method="post">
'''
        idx = 0
        for S in parsed_scenes.keys():
            gc.collect()
            sceneId = parsed_scenes[S]
            if not sceneId in SCENEDIC.values():
                forms += f'''
<div>
<input type="checkbox" name="active" value="{idx}">
<input type="text" name="caption" value="{S}">
<input type="hidden" name="sID" value="{sceneId}">
</div>
'''
                idx += 1
                gc.collect()
            
        forms += f'''
<hr><div>
<button type="submit">{USER.DESC_BUTTON_REGIST}</button>
<button type="submit" name="action" value="cancel">{USER.DESC_BUTTON_REGISTCANCEL}</button>
</div></form></body></html>
'''
        gc.collect()
        return forms, 200, html_headers
        
    # Regist selected Switchbot scenes
    @app.route('/regapply', methods=['POST'])
    async def _regapply(request):
        global parsed_scenes
        if request.form.get('action')!='cancel':
            actives  = request.form.getlist('active')
            captions = request.form.getlist('caption')
            sIDs = request.form.getlist('sID')
            if '(_initial_)' in SCENEDIC.keys():
                SCENEDIC.clear()
            for ID in actives:
                id = int(ID)
                SCENEDIC[captions[id]] = sIDs[id]
                print(f'SCENEDIC add:("{captions[id]}":"{sIDs[id]}")')
            SaveSceneDic()

        del parsed_scenes
        parsed_scenes = None
        gc.collect()
        return html_backhome, 200, html_headers

    log("Start Web server.")
    await app.run(port=80)

async def web():
    await web_server()


async def checkScheduleAndKick(dtime):
    for S in DataBase:
        # S = (NAME,WEEKDAYS,HOUR,MINUTE,SECOND,YEAR,MONTH,DAY,SCENENAME,ACTIVE)
        # Check schedule active and weekdays
        if S[9] and dtime[6] in S[1]:
            # Hour?
            if S[2]<0 or dtime[3]==S[2]:
                # Minute?
                if S[3]<0 or dtime[4]==S[3]:
                    # Second?
                    if dtime[5]==S[4]:
                        scenename = S[8]
                        if scenename in SCENEDIC:
                            await ExecuteScene(SCENEDIC[scenename])
                        else:
                            log(f'Scene name "{scenename}" does not found.')

wdt = None
def WDTstart():
    global wdt
    wdt = machine.WDT(timeout=8000)
    
def WDTfeed():
    global wdt
    if wdt!=None:
        wdt.feed()

async def worker():
    global testtime
    global testscene
    global adjusttime

    log('Start Worker.')
    nowtime = OffsetUTCtime()
    adjusttime = nowtime+12*3600
    activetime = nowtime+1
    execNow = -1

    WDTstart()
    WDTfeed()
    while True:
        #ledon()
        rtime = OffsetUTCtime()
        dtime = utime.localtime(rtime)
        gc.collect()
        if execNow != dtime[5]:
            execNow = dtime[5]

            # Active Sense
            if rtime>=activetime:
                logActive()
                activetime = OffsetUTCtime()+10

            # Kick Test
            if rtime==testtime:
                await ExecuteScene(testscene)
                log("Kick test executed.")

            await checkScheduleAndKick(dtime)
                                    
            # Time Adjust
            if rtime>=adjusttime:
                if AdjustTime()==0:
                    adjusttime = OffsetUTCtime()+5*60
                else:
                    adjusttime = OffsetUTCtime()+12*3600

        #ledoff()
        WDTfeed()
        await uasyncio.sleep(0.2)


def inet_aton(ip_str):
    return bytes(map(int, ip_str.split(".")))

async def mDNS():
    await mDNSresponder()
    while True:
        await uasyncio.sleep(24*3600)

async def mDNSresponder():
    MDNS_GROUP = "224.0.0.251"
    MDNS_PORT = 5353

    ip = network.WLAN(network.STA_IF).ifconfig()[0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('', MDNS_PORT))
    except Exception:
        log('Start mDNS responder failure... (optional)')
        return
    mreq = struct.pack("4sl", inet_aton(MDNS_GROUP), 0)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    log("Start mDNS responder. (optional)")
    while True:
        await uasyncio.sleep(0.1)

        rlist, _, _ = select.select([sock], [], [], 0)
        if not rlist: continue

        data, addr = sock.recvfrom(1024)
        #print(f"Received mDNS query from {addr}: {data.hex()}")

        if b'swbotkicker' in data:
            #print("Sending mDNS response...")
            response = (
                b'\x00\x00'  # Transaction ID
                b'\x84\x00'  # Flags (QR=1, OPCODE=0, AA=1, TC=0, RD=0, RA=0, Z=0, AD=0, CD=0, RCODE=0)
                b'\x00\x00'  # Questions = 1
                b'\x00\x01'  # Answers = 1（A）
                b'\x00\x00'  # Authority RRs = 0
                b'\x00\x00'  # Additional RRs = 0

                # A Record (IPV4)
                b'\x0Bswbotkicker\x05local\x00'
                b'\x00\x01'  # Type: A
                b'\x00\x01'  # Class: IN
                b'\x00\x00\x01\x2C'  # TTL = 5*60s
                b'\x00\x04'  # Data length = 4
                + inet_aton(ip)  # IPv4 Address
            )

            sock.sendto(response, (MDNS_GROUP, MDNS_PORT))
            sock.sendto(response, (MDNS_GROUP, MDNS_PORT))
            sock.sendto(response, (MDNS_GROUP, MDNS_PORT))
            #print(f"mDNS response sent: {response.hex()}")


def AppInit():
    ledon()
    loginit()
    ResetRTC()
    DispBootReason()
    DispMACAddress()
    ConnectNetwork()
    while AdjustTime()==0:
        log('Retry')
        utime.sleep(2)

    print(f'NOW(Offseted): {DatetimeString(OffsetUTCtime())}')
    gc.collect()
    ledoff()

    SetupSceneDic()
    SetupDataBase()

def AppStart():
    gc.collect()
    uasyncio.create_task(web())
    uasyncio.create_task(worker())
    uasyncio.run(mDNS())

def AppMain():
    AppInit()
    AppStart()
    

AppMain()
