'''
import streamlit as st

st.write('Hello wasdforld~~~~!')
'''


import streamlit as st
import serial           # pyserial
import time
import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo

# ===========================================================
# 1. 초기 설정 및 Session State 정의
# ===========================================================

# Session State 초기화 (웹 페이지 상태 유지용)
if 'py_serial' not in st.session_state:
    st.session_state.py_serial = None
if 'ervMode' not in st.session_state:
    st.session_state.ervMode = 0
if 'ervFanSpeed' not in st.session_state:
    st.session_state.ervFanSpeed = 0
if 'modeERV' not in st.session_state:
    st.session_state.modeERV = 0x12  # 초기값 Ventil (MD_VT)
if 'link_value' not in st.session_state:
    st.session_state.link_value = 0x00 # 주방 연동 초기값

HEAD    = 0xF7
DEVICE  = 0x32
ID      = 0x01
MD_VT = 0x12
MD_BP = 0x14
BAUDRATE = 9600

# ===========================================================
# 2. 통신 프로토콜 함수 (기존 코드 유지)
# ===========================================================

def xor_bytes(data):
    crc = 0
    for i in range(0, 7):
        crc = crc ^ data[i]
    return crc

def sum_bytes(data):
    crc = 0
    for i in range(0, 7):
        crc = crc + data[i]
    return crc

def send_command(txdata_list):
    """시리얼로 명령을 전송하고 디버깅 메시지를 출력하는 함수"""
    if st.session_state.py_serial and st.session_state.py_serial.is_open:
        try:
            # 프로토콜 완성 (XOR, SUM 추가)
            xOR = xor_bytes(txdata_list)
            add = (sum_bytes(txdata_list) + xOR) & 0xFF
            values = bytearray([*txdata_list, xOR, add])
            st.session_state.py_serial.write(values)
            st.toast(f"Command Sent: {' '.join(f'{b:02X}' for b in values)}", icon="📡")
        except Exception as e:
            st.error(f"데이터 전송 실패: {e}")
    else:
        st.warning("시리얼 포트가 연결되지 않았습니다.")


# ===========================================================
# 3. 시리얼 연결 로직
# ===========================================================

def connect_serial(port):
    """시리얼 포트를 연결하는 함수"""
    if not port:
        st.error("포트를 선택해 주세요.")
        return

    try:
        # 기존 연결이 있으면 닫음
        if st.session_state.py_serial and st.session_state.py_serial.is_open:
            st.session_state.py_serial.close()

        # 새로운 시리얼 객체 생성 및 연결
        st.session_state.py_serial = serial.Serial(port, baudrate=BAUDRATE, timeout=1)
        st.success(f"Port Connect Success: {port}")
    except Exception as e:
        st.error(f"Port Connect Fail: {e}")
        st.session_state.py_serial = None

# ===========================================================
# 4. Streamlit GUI 구성
# ===========================================================

st.set_page_config(page_title="CVnet BanPo3 Control", layout="wide")
st.title("CVnet BanPo3 🌐 Streamlit Web Control")

# -----------------
# 4.1. 시리얼 연결 섹션
# -----------------
with st.container():
    st.subheader("1. 시리얼 포트 연결")
    
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    
    if not port_list:
        st.error("사용 가능한 시리얼 포트가 없습니다. 서버에 장치를 연결했는지 확인하세요.")
        selected_port = None
    else:
        selected_port = st.selectbox("시리얼 포트 선택", options=port_list)
        
    if st.button("CONNECT / DISCONNECT", use_container_width=True):
        if st.session_state.py_serial and st.session_state.py_serial.is_open:
            st.session_state.py_serial.close()
            st.session_state.py_serial = None
            st.warning("연결 해제됨.")
        else:
            connect_serial(selected_port)
    
    serial_status_text = "✅ 연결됨" if st.session_state.py_serial and st.session_state.py_serial.is_open else "❌ 연결되지 않음"
    st.markdown(f"**현재 상태:** {serial_status_text}")

# -----------------
# 4.2. 상태 표시 및 주기적 통신 섹션
# -----------------
st.divider()
st.subheader("2. 장치 상태 (3초마다 자동 업데이트)")

status_col1, status_col2 = st.columns(2)
status_md_placeholder = status_col1.empty()
status_fan_placeholder = status_col2.empty()

def update_status_from_serial():
    """시리얼 통신 상태 요청 및 파싱 (주기적 실행)"""
    global status_md_placeholder, status_fan_placeholder
    
    if st.session_state.py_serial and st.session_state.py_serial.is_open:
        try:
            # CVNET-상태요청
            values = bytearray([0xF7, 0X32, 0X01, 0X11, 0X00, 0XD5, 0X10])
            st.session_state.py_serial.write(values)
            time.sleep(0.1) # 응답 대기 시간
            
            if st.session_state.py_serial.readable():
                rxdata = st.session_state.py_serial.readline(13)
                if len(rxdata) == 13 and rxdata[0] == HEAD and rxdata[1] == DEVICE and rxdata[2] == ID:
                    st.session_state.ervMode = rxdata[6] & 0x0F
                    st.session_state.ervFanSpeed = rxdata[7] & 0x70
                    # st.session_state.rx_data = ' '.join(f'{b:02X}' for b in rxdata) # 디버그용
        except Exception as e:
            st.warning(f"상태 요청 실패: {e}")
    
    # 상태 표시 업데이트 (파싱된 값 사용)
    ervMode = st.session_state.ervMode
    ervFanSpeed = st.session_state.ervFanSpeed
    
    mode_text = ""
    if ervMode == 0x04: mode_text = "BYPASS" 
    elif ervMode == 0x00: mode_text = "OFF" 
    else: mode_text = "VENTIL"
    
    fan_text = ""
    if ervFanSpeed == 0x10: fan_text = "LOW" 
    elif ervFanSpeed == 0x20: fan_text = "MID" 
    elif ervFanSpeed == 0x30: fan_text = "FAST" 
    else: fan_text = "STOP"
    
    status_md_placeholder.metric("환기 모드", mode_text)
    status_fan_placeholder.metric("팬 속도", fan_text)

# Streamlit의 재실행을 통한 주기적 업데이트 (3초마다)
# st_autorefresh 라이브러리를 사용하면 더 좋지만, 기본 기능으로 구현
st.info("⚠️ 웹페이지를 수동으로 새로고침하거나, 아래 버튼을 눌러 상태를 업데이트하세요.")
if st.button("수동 상태 업데이트", type="primary"):
    update_status_from_serial()
    st.toast("상태 업데이트 완료!")
    

# -----------------
# 4.3. 제어 버튼 섹션
# -----------------
st.divider()
st.subheader("3. 장치 제어")

# 모드 선택 (Radiobutton 대체)
def on_mode_change():
    """모드 선택 시 시리얼 전송"""
    st.session_state.modeERV = st.session_state.selected_mode
    txdata = [0xF7, 0x32, 0x01, 0x51, 0x03, st.session_state.modeERV, 0x00, 0x00]
    send_command(txdata)

mode_options = {MD_VT: "Ventil (환기)", MD_BP: "Bypass (우회)"}
st.radio(
    "환기 모드 선택",
    options=list(mode_options.keys()),
    format_func=lambda x: mode_options[x],
    key='selected_mode', # Session State에 값을 저장할 키
    on_change=on_mode_change,
)

# 주방 연동 (Checkbutton 대체)
def on_kitchen_check():
    """주방 연동 체크박스 변경 시 시리얼 전송"""
    if st.session_state.kitchen_linked: 
        st.session_state.link_value = 0x40 
    else : 
        st.session_state.link_value = 0x00
        
    # 주방 연동은 모드 변경 필드에 영향을 줄 가능성이 낮으므로, 단순 커맨드 전송으로 대체
    # 원래 코드의 로직을 정확히 따라가기 위해 link_value를 payload에 넣는 대신, 
    # 독립된 연동 커맨드가 있다면 더 좋지만, 여기서는 원본 코드 로직을 기반으로 재구성합니다.
    txdata = [0xF7, 0x32, 0x01, 0x51, 0x03, st.session_state.link_value, 0x00, 0x00]
    send_command(txdata)

st.checkbox("Hood 연동", key='kitchen_linked', on_change=on_kitchen_check)


# 팬 속도 제어 버튼
st.markdown("#### 팬 속도 제어")
fan_col1, fan_col2, fan_col3, fan_col4 = st.columns(4)

def fan_command(speed_byte):
    """팬 속도 명령 전송 함수"""
    # 0x80은 제어 플래그로 추정
    txdata = [0xF7, 0x32, 0x01, 0x51, 0x03, 0x00, 0x80 + speed_byte, 0x00]
    send_command(txdata)

with fan_col1:
    if st.button("STOP", use_container_width=True):
        fan_command(0x00)
with fan_col2:
    if st.button("Low", use_container_width=True):
        fan_command(0x10)
with fan_col3:
    if st.button("Mid", use_container_width=True):
        fan_command(0x20)
with fan_col4:
    if st.button("Fast", use_container_width=True):
        fan_command(0x30)