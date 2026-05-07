import oracledb
import sys

# [요구사항 3] 지원 은행 상수
SUPPORTED_BANKS = ["하나은행", "우리은행", "국민은행", "신한은행", "기업은행"]


class DatabaseManager:
    """데이터베이스 연결 및 기본 세팅 관리 클래스"""

    def __init__(self):
        self.config = {
            "user": "system",
            "password": "Manager1",
            "dsn": "localhost:1521/FREE",
        }

    def get_connection(self):
        try:
            return oracledb.connect(**self.config)
        except Exception as e:
            print(f"\n[오류] DB 연결 실패: {e}")
            return None


class BankSystem:
    """은행의 주요 비즈니스 로직을 담당하는 클래스"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.current_user = None

    # --- [회원/인증 관련] ---
    def register(self):
        conn = self.db.get_connection()
        if not conn:
            return
        cursor = conn.cursor()

        print("\n--- 회원가입 ---")
        uid, pw, name, phone = (
            input("아이디: "),
            input("비밀번호: "),
            input("이름: "),
            input("연락처: "),
        )
        is_admin = "Y" if uid.lower() == "admin" else "N"

        try:
            cursor.execute(
                """
                INSERT INTO users (user_id, password, user_name, phone, is_admin) 
                VALUES (:1, :2, :3, :4, :5)
            """,
                [uid, pw, name, phone, is_admin],
            )
            conn.commit()
            print(f"회원가입 완료! (권한: {'관리자' if is_admin == 'Y' else '일반'})")
        except:
            print("중복된 아이디가 존재하거나 데이터가 올바르지 않습니다.")
        finally:
            conn.close()

    def login(self):
        conn = self.db.get_connection()
        if not conn:
            return False
        cursor = conn.cursor()

        uid, pw = input("아이디: "), input("비밀번호: ")
        cursor.execute(
            "SELECT user_id, user_name, is_admin FROM users WHERE user_id = :1 AND password = :2",
            [uid, pw],
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            self.current_user = {"id": user[0], "name": user[1], "is_admin": user[2]}
            print(f"{user[1]}님, 로그인 성공!")
            return True
        print("아이디나 비밀번호가 틀렸습니다.")
        return False

    def logout(self):
        self.current_user = None
        print("로그아웃 되었습니다.")

    # --- [계좌 관리 관련] ---
    def create_account(self):
        print(f"\n가능 은행: {SUPPORTED_BANKS}")
        bank = input("은행명: ")
        if bank not in SUPPORTED_BANKS:
            print("지원하지 않는 은행입니다.")
            return

        acc_num, alias = input("계좌번호: "), input("계좌 별칭: ")
        try:
            balance = int(input("최초 입금액 (1000원 이상): "))
            if balance < 1000:
                print("1000원 이상 입금해야 합니다.")
                return

            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO account (account_number, user_id, bank_name, balance, alias) 
                VALUES (:1, :2, :3, :4, :5)
            """,
                [acc_num, self.current_user["id"], bank, balance, alias],
            )

            cursor.execute(
                "INSERT INTO transaction (account_number, type, amount) VALUES (:1, '입금', :2)",
                [acc_num, balance],
            )
            conn.commit()
            print("계좌 생성 및 등록 완료!")
        except Exception as e:
            print(f"오류: {e}")
        finally:
            conn.close()

    def view_my_accounts(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT bank_name, account_number, balance, alias FROM account WHERE user_id = :1",
            [self.current_user["id"]],
        )
        rows = cursor.fetchall()

        print(f"\n--- {self.current_user['name']}님의 전체 계좌 목록 ---")
        for r in rows:
            print(f"[{r[0]}] {r[1]} | 잔액: {r[2]}원 | 별칭: {r[3]}")
        conn.close()

    def update_alias(self):
        acc_num = input("별칭을 수정할 계좌번호: ")
        new_alias = input("새로운 별칭: ")
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT alias FROM account WHERE account_number = :1", [acc_num]
            )
            res = cursor.fetchone()
            if res and res[0] == new_alias:
                print("기존과 동일한 별칭으로는 수정이 불가능합니다.")
                return

            cursor.execute(
                "UPDATE account SET alias = :1 WHERE account_number = :2",
                [new_alias, acc_num],
            )
            conn.commit()
            print("별칭 수정 완료!")
        finally:
            conn.close()

    # --- [금융 업무 관련] ---
    def deposit_withdraw(self, mode):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        acc_num = input("계좌번호: ")
        cursor.execute(
            "SELECT balance FROM account WHERE account_number = :1", [acc_num]
        )
        row = cursor.fetchone()

        if not row:
            print("존재하지 않는 계좌입니다.")
            conn.close()
            return

        amount = int(input(f"{mode}할 금액: "))
        try:
            if mode == "출금":
                if row[0] < amount:
                    print("잔액이 부족합니다.")
                    return
                cursor.execute(
                    "UPDATE account SET balance = balance - :1 WHERE account_number = :2",
                    [amount, acc_num],
                )
            else:
                cursor.execute(
                    "UPDATE account SET balance = balance + :1 WHERE account_number = :2",
                    [amount, acc_num],
                )

            cursor.execute(
                "INSERT INTO transaction (account_number, type, amount) VALUES (:1, :2, :3)",
                [acc_num, mode, amount],
            )
            conn.commit()
            print(f"{mode} 완료!")
        except Exception as e:
            conn.rollback()
            print(f"오류 발생: {e}")
        finally:
            conn.close()

    def transfer(self):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            from_acc = input("내 계좌번호: ")
            to_acc = input("상대방 계좌번호: ")
            amount = int(input("이체 금액: "))

            if amount <= 0:
                print("이체 금액은 0원보다 커야 합니다.")
                return

            cursor.execute(
                "SELECT balance FROM account WHERE account_number = :1 AND user_id = :2",
                [from_acc, self.current_user["id"]],
            )
            row = cursor.fetchone()

            if not row or row[0] < amount:
                print("잔액이 부족하여 이체가 취소되었습니다.")
                return

            # 트랜잭션 시작
            cursor.execute(
                "UPDATE account SET balance = balance - :1 WHERE account_number = :2",
                [amount, from_acc],
            )
            cursor.execute(
                "UPDATE account SET balance = balance + :1 WHERE account_number = :2",
                [amount, to_acc],
            )
            cursor.execute(
                """
                INSERT INTO transaction (account_number, type, amount, target_account) 
                VALUES (:1, '이체', :2, :3)
            """,
                [from_acc, amount, to_acc],
            )

            conn.commit()
            print("계좌이체 성공!")
        except Exception:
            conn.rollback()
            print("작업 중 오류 발생으로 모든 작업이 취소되었습니다.")
        finally:
            conn.close()

    def view_transactions(self):
        acc_num = input("내역을 조회할 계좌번호: ")
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT type, amount, target_account, transaction_date 
            FROM transaction 
            WHERE account_number = :1 
            ORDER BY transaction_date DESC
        """,
            [acc_num],
        )
        rows = cursor.fetchall()

        print(f"\n--- [{acc_num}] 거래 내역 ---")
        for r in rows:
            target = f" -> 상대계좌: {r[2]}" if r[2] else ""
            print(f"[{r[3].strftime('%m-%d %H:%M')}] {r[0]}: {r[1]}원{target}")
        conn.close()

    # --- [관리자 관련] ---
    def admin_menu(self):
        while True:
            print("\n--- [관리자 전용 메뉴] ---")
            print("1.사용자 정보 전체 조회 2.사용자 계정 삭제 3.메인으로 이동")
            choice = input("선택: ")

            conn = self.db.get_connection()
            cursor = conn.cursor()
            if choice == "1":
                cursor.execute("SELECT user_id, user_name, phone, is_admin FROM users")
                for r in cursor.fetchall():
                    print(
                        f"ID: {r[0]} | 이름: {r[1]} | 연락처: {r[2]} | 관리자: {r[3]}"
                    )
            elif choice == "2":
                target_id = input("삭제할 사용자 ID: ")
                if target_id == self.current_user["id"]:
                    print("관리자 본인 계정은 삭제 불가합니다.")
                else:
                    cursor.execute("DELETE FROM users WHERE user_id = :1", [target_id])
                    conn.commit()
                    print(f"{target_id} 계정이 삭제되었습니다.")
            elif choice == "3":
                conn.close()
                break
            conn.close()


class App:
    """메인 실행 애플리케이션 클래스"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.bank = BankSystem(self.db_manager)

    def run(self):
        while True:
            choice = input("\n[1]회원가입 [2]로그인 [3]종료\n입력: ")
            if choice == "1":
                self.bank.register()
            elif choice == "2":
                if self.bank.login():
                    self.user_menu()
            elif choice == "3":
                print("시스템을 종료합니다.")
                sys.exit()

    def user_menu(self):
        while True:
            user = self.bank.current_user
            print(f"\n--- 은행 메뉴 [{user['name']}] ---")
            print(
                "1.계좌생성 2.계좌조회 3.입금 4.출금 5.계좌이체 6.별칭수정 7.내역조회 8.로그아웃"
            )

            if user["is_admin"] == "Y":
                print("9.관리자 전용 메뉴")

            m = input("선택: ")
            if m == "1":
                self.bank.create_account()
            elif m == "2":
                self.bank.view_my_accounts()
            elif m == "3":
                self.bank.deposit_withdraw("입금")
            elif m == "4":
                self.bank.deposit_withdraw("출금")
            elif m == "5":
                self.bank.transfer()
            elif m == "6":
                self.bank.update_alias()
            elif m == "7":
                self.bank.view_transactions()
            elif m == "8":
                self.bank.logout()
                break
            elif m == "9" and user["is_admin"] == "Y":
                self.bank.admin_menu()


if __name__ == "__main__":
    app = App()
    app.run()
