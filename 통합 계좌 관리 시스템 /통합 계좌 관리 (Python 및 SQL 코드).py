import oracledb
import sys

current_user = None

# [요구사항 3] 계좌등록은 통합계좌 관리시스템에서 제공하는 은행에 한해서만 가능
SUPPORTED_BANKS = ["하나은행", "우리은행", "국민은행", "신한은행", "기업은행"]

# --- [DB 연결 함수] ---
def get_connection():
    try:
        return oracledb.connect(user="system", password="Manager1", dsn="localhost:1521/FREE")
    except Exception as e:
        print(f"\n[오류] DB 연결 실패: {e}")
        return None

# --- [기능 1: 회원가입/로그인] ---
def register():
    conn = get_connection()
    if not conn: return
    cursor = conn.cursor()
    print("\n--- 회원가입 ---")
    uid, pw, name, phone = input("아이디: "), input("비밀번호: "), input("이름: "), input("연락처: ")
    
    # [요구사항 14] 관리자 계정으로 로그인하기 위한 사전 설정
    is_admin = 'Y' if uid.lower() == 'admin' else 'N'

    try:
        cursor.execute("""
            INSERT INTO users (user_id, password, user_name, phone, is_admin) 
            VALUES (:1, :2, :3, :4, :5)
        """, [uid, pw, name, phone, is_admin])
        conn.commit()
        print(f"회원가입 완료! (권한: {'관리자' if is_admin == 'Y' else '일반'})")
    except:
        print("중복된 아이디가 존재합니다.")
    finally:
        conn.close()

def login():
    global current_user
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    uid, pw = input("아이디: "), input("비밀번호: ")
    
    # [요구사항 1] 사용자는 로그인 후 통합계좌 관리시스템의 서비스를 사용할 수 있다.
    # [요구사항 14] 로그인을 통해 관리자 권한 여부를 판단함.
    cursor.execute("SELECT user_id, user_name, is_admin FROM users WHERE user_id = :1 AND password = :2", [uid, pw])
    user = cursor.fetchone()
    conn.close()
    
    if user:
        current_user = {"id": user[0], "name": user[1], "is_admin": user[2]}
        print(f"{user[1]}님, 로그인 성공!")
        return True
    print("아이디나 비밀번호가 틀렸습니다."); return False

# --- [기능 2: 계좌 관리] ---
def create_account():
    # [요구사항 3, 5] 사용자는 제공하는 은행(하나, 우리, 국민, 신한, 기업)에 한해 계좌를 생성/등록할 수 있다.
    print(f"\n가능 은행: {SUPPORTED_BANKS}")
    bank = input("은행명: ")
    if bank not in SUPPORTED_BANKS:
        print("지원하지 않는 은행입니다."); return
    
    acc_num, alias = input("계좌번호: "), input("계좌 별칭: ")
    try:
        # [요구사항 12] 사용자는 계좌를 생성할 수 있고, 최초 생성 시 입금액은 1000원 이상이어야 한다.
        balance = int(input("최초 입금액 (1000원 이상): "))
        if balance < 1000: 
            print("1000원 이상 입금해야 합니다."); return
        
        conn = get_connection(); cursor = conn.cursor()
        # [요구사항 2] 계좌 정보는 은행명, 계좌번호, 계좌주명, 잔액, 별칭으로 구성된다.
        cursor.execute("""
            INSERT INTO account (account_number, user_id, bank_name, balance, alias) 
            VALUES (:1, :2, :3, :4, :5)
        """, [acc_num, current_user['id'], bank, balance, alias])
        
        # [요구사항 6] 사용자는 계좌번호로 계좌 정보를 검색(생성 내역 기록)할 수 있다.
        cursor.execute("INSERT INTO transaction (account_number, type, amount) VALUES (:1, '입금', :2)", [acc_num, balance])
        conn.commit()
        print("계좌 생성 및 등록 완료!"); conn.close()
    except Exception as e: 
        print(f"오류: {e}")

def view_my_accounts():
    # [요구사항 7, 8] 전체 계좌정보 리스트 및 별칭별/계좌번호별/은행별 리스트를 검색할 수 있다.
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT bank_name, account_number, balance, alias FROM account WHERE user_id = :1", [current_user['id']])
    rows = cursor.fetchall()
    
    print(f"\n--- {current_user['name']}님의 전체 계좌 목록 ---")
    for r in rows: 
        print(f"[{r[0]}] {r[1]} | 잔액: {r[2]}원 | 별칭: {r[3]}")
    conn.close()

def update_alias():
    # [요구사항 4] 사용자는 계좌번호의 별칭을 수정할 수 있다. 단, 같은 별칭으로는 수정이 불가하다.
    acc_num = input("별칭을 수정할 계좌번호: ")
    new_alias = input("새로운 별칭: ")
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT alias FROM account WHERE account_number = :1", [acc_num])
        res = cursor.fetchone()
        
        # [요구사항 4-2] 같은 별칭으로 수정 불가 조건 확인
        if res and res[0] == new_alias:
            print("기존과 동일한 별칭으로는 수정이 불가능합니다."); return
        
        # [요구사항 5] 사용자는 계좌의 별칭을 수정할 수 있다.
        cursor.execute("UPDATE account SET alias = :1 WHERE account_number = :2", [new_alias, acc_num])
        conn.commit(); print("별칭 수정 완료!")
    finally: conn.close()

# --- [기능 3: 금융 업무] ---
def deposit_withdraw(mode):
    # [요구사항 9] 각 계좌들은 입금, 출금이 가능하다.
    conn = get_connection(); cursor = conn.cursor()
    acc_num = input("계좌번호: ")
    cursor.execute("SELECT balance FROM account WHERE account_number = :1", [acc_num])
    row = cursor.fetchone()
    if not row: print("존재하지 않는 계좌입니다."); return

    amount = int(input(f"{mode}할 금액: "))
    try:
        if mode == "출금":
            if row[0] < amount: 
                print("잔액이 부족합니다."); return
            cursor.execute("UPDATE account SET balance = balance - :1 WHERE account_number = :2", [amount, acc_num])
        else:
            cursor.execute("UPDATE account SET balance = balance + :1 WHERE account_number = :2", [amount, acc_num])
        
        # 거래 내역 기록
        cursor.execute("INSERT INTO transaction (account_number, type, amount) VALUES (:1, :2, :3)", [acc_num, mode, amount])
        conn.commit(); print(f"{mode} 완료!")
    except: 
        conn.rollback(); 
        print("오류 발생")
    finally: 
        conn.close()

def transfer():
    # [요구사항 9, 10, 11, 13] 계좌이체 관련 복합 요구사항 처리
    conn = get_connection(); cursor = conn.cursor()
    try:
        from_acc = input("내 계좌번호: ")
        to_acc = input("상대방 계좌번호: ")
        amount = int(input("이체 금액: "))
        
        # [요구사항 10] 계좌이체 시 0원 초과 금액만 가능하다.
        if amount <= 0: 
            print("이체 금액은 0원보다 커야 합니다."); return

        cursor.execute("SELECT balance FROM account WHERE account_number = :1 AND user_id = :2", [from_acc, current_user['id']])
        row = cursor.fetchone()
        
        # [요구사항 11] 계좌이체 시 이체 금액이 잔액보다 많은 경우 이체가 취소된다.
        if not row or row[0] < amount: 
            print("잔액이 부족하여 이체가 취소되었습니다."); return

        # [요구사항 13] 계좌이체 작업 중 출금, 입금 업무에서 문제가 발생하는 경우 모든 작업이 취소된다 (트랜잭션 관리).
        cursor.execute("UPDATE account SET balance = balance - :1 WHERE account_number = :2", [amount, from_acc])
        cursor.execute("UPDATE account SET balance = balance + :1 WHERE account_number = :2", [amount, to_acc])
        cursor.execute("""
            INSERT INTO transaction (account_number, type, amount, target_account) 
            VALUES (:1, '이체', :2, :3)
        """, [from_acc, amount, to_acc])
        
        conn.commit(); print("계좌이체 성공!")
    except Exception:
        # [요구사항 13] 오류 발생 시 롤백 처리
        conn.rollback(); print("작업 중 오류 발생으로 모든 작업이 취소되었습니다.")
    finally: conn.close()

def view_transactions():
    # [요구사항 6] 사용자는 계좌번호로 거래내역 정보를 검색할 수 있다.
    acc_num = input("내역을 조회할 계좌번호: ")
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("""
        SELECT type, amount, target_account, transaction_date 
        FROM transaction 
        WHERE account_number = :1 
        ORDER BY transaction_date DESC
    """, [acc_num])
    rows = cursor.fetchall()
    
    print(f"\n--- [{acc_num}] 거래 내역 ---")
    for r in rows:
        target = f" -> 상대계좌: {r[2]}" if r[2] else ""
        print(f"[{r[3].strftime('%m-%d %H:%M')}] {r[0]}: {r[1]}원{target}")
    conn.close()

# --- [기능 4: 관리자 전용] ---
def admin_menu():
    # [요구사항 14] 관리자메뉴에서는 관리자 계정으로 로그인 후, 사용자 정보를 조회, 수정, 삭제할 수 있다.
    while True:
        print("\n--- [관리자 전용 메뉴] ---")
        print("1.사용자 정보 전체 조회 2.사용자 계정 삭제 3.메인으로 이동")
        choice = input("선택: ")
        
        conn = get_connection(); cursor = conn.cursor()
        if choice == "1":
            # 사용자 정보 조회
            cursor.execute("SELECT user_id, user_name, phone, is_admin FROM users")
            for r in cursor.fetchall():
                print(f"ID: {r[0]} | 이름: {r[1]} | 연락처: {r[2]} | 관리자: {r[3]}")
        elif choice == "2":
            # 사용자 정보 삭제
            target_id = input("삭제할 사용자 ID: ")
            if target_id == current_user['id']: 
                print("관리자 본인 계정은 삭제 불가합니다.")
            else:
                cursor.execute("DELETE FROM users WHERE user_id = :1", [target_id])
                conn.commit(); print(f"{target_id} 계정이 삭제되었습니다.")
        elif choice == "3":
            conn.close(); break
        conn.close()

# --- [메인 실행 흐름] ---
def main():
    while True:
        choice = input("\n[1]회원가입 [2]로그인 [3]종료\n입력: ")
        if choice == "1": register()
        elif choice == "2":
            if login():
                while True:
                    # [요구사항 1~9 메뉴 구성]
                    print(f"\n--- 은행 메뉴 [{current_user['name']}] ---")
                    print("1.계좌생성 2.계좌조회 3.입금 4.출금 5.계좌이체 6.별칭수정 7.내역조회 8.로그아웃")
                    
                    # [요구사항 14] 관리자 계정일 경우에만 전용 메뉴 표시
                    if current_user['is_admin'] == 'Y':
                        print("9.관리자 전용 메뉴")
                    
                    m = input("선택: ")
                    if m == "1": create_account() # 요구사항 3, 5, 12
                    elif m == "2": view_my_accounts() # 요구사항 7, 8
                    elif m == "3": deposit_withdraw("입금") # 요구사항 9
                    elif m == "4": deposit_withdraw("출금") # 요구사항 9
                    elif m == "5": transfer() # 요구사항 9, 10, 11, 13
                    elif m == "6": update_alias() # 요구사항 4, 5
                    elif m == "7": view_transactions() # 요구사항 6
                    elif m == "8": break
                    elif m == "9" and current_user['is_admin'] == 'Y': 
                        admin_menu() # 요구사항 14
        elif choice == "3": sys.exit()

if __name__ == "__main__":
    main()
