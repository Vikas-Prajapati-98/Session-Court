import requests

# ----------------- API Client -----------------
class APIClient:
    BASE_URL = "http://192.168.1.81:8000/search"

    def __init__(self):
        self.session = requests.Session()

    def post(self, endpoint: str, params: dict):
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.post(
                url,
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=params
            )
            response_data = response.json()
            return {"status": response.status_code, "data": response_data}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ----------------- Pretty Print Function -----------------
def pretty_print(response) -> str:
    output = []

    if response.get("status") != 200:
        output.append(f"[ERROR] Request failed. Status: {response.get('status')}")
        if "error" in response:
            output.append(f"[DETAIL] {response['error']}")
        return "\n".join(output)

    data = response["data"]
    if isinstance(data, list):
        for i, item in enumerate(data, start=1):
            output.append(f"\n========== Case {i} Details ==========")
            for key, value in item.items():
                formatted_key = key.replace("_", " ").title()
                output.append(f"{formatted_key}: {value}")
    else:
        output.append("\n========== Case Details ==========")
        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            output.append(f"{formatted_key}: {value}")

    return "\n".join(output)


# ----------------- API Test Manager -----------------
class APITestManager:
    def __init__(self):
        self.client = APIClient()
        self.menu = {
            "A. Case Search": {
                "1. CNR Search": self.cnr_search,
                "2. Filing Search": self.filing_search,
                "3. Registration Search": self.registration_search,
                "4. FIR Search": self.fir_search,
                "5. Party Search": self.party_search,
                "6. Subordinate Court Search": self.subordinate_search,
            },
            "B. Advocate Search": {
                "1. Advocate Search": self.advocate_search,
            },
            "C. Cause List": {
                "1. Cause List Search": self.cause_list_search,
            },
            "D. Lok Adalat": {
                "1. Lok Adalat Search": self.lokadalat_search,
            },
            "E. Caveat Search": {
                "1. Caveat Search": self.caveat_search,
            },
            "F. Panel Search": {
                "1. Pre-Panel Search": self.pre_panel_search,
            }
        }

    def run(self):
        while True:
            print("\n========== API Test Menu ==========")
            for group_name, actions in self.menu.items():
                print(f"\n{group_name}")
                for key, value in actions.items():
                    print(f"   {key}")

            choice = input("\nEnter search number (e.g., A1 for CNR) or Q to quit: ").strip().upper()
            if choice == "Q":
                break

            selected = self._resolve_choice(choice)
            if selected:
                selected()
            else:
                print("[ERROR] Invalid choice. Please try again.")

    def _resolve_choice(self, choice):
        mapping = {
            "A1": self.cnr_search,
            "A2": self.filing_search,
            "A3": self.registration_search,
            "A4": self.fir_search,
            "A5": self.party_search,
            "A6": self.subordinate_search,
            "B1": self.advocate_search,
            "C1": self.cause_list_search,
            "D1": self.lokadalat_search,
            "E1": self.caveat_search,
            "F1": self.pre_panel_search,
        }
        return mapping.get(choice)

    # ========== Individual Search Methods ==========

    def cnr_search(self):
        cnr_number = input("Enter CNR Number: ")
        response = self.client.post("cnr", {"cnr_number": cnr_number})
        result = pretty_print(response)
        print(result)

    def filing_search(self):
        filing_number = input("Enter Filing Number (e.g., F/2025/00123): ")
        year = input("Enter Year: ")
        response = self.client.post("filing", {
            "filing_number": filing_number,
            "year": year
        })
        result = pretty_print(response)
        print(result)

    def registration_search(self):
        case_type = input("Enter Case Type: ")
        registration_number = input("Enter Registration Number (e.g., REG/2025/78456): ")
        year = input("Enter Year: ")
        response = self.client.post("registration", {
            "case_type": case_type,
            "registration_number": registration_number,
            "year": year
        })
        result = pretty_print(response)
        print(result)

    def fir_search(self):
        state = input("Enter State: ")
        district = input("Enter District: ")
        police_station = input("Enter Police Station: ")
        fir_number = input("Enter FIR Number (e.g., FIR123/2025): ")
        year = input("Enter Year: ")
        status = input("Enter Status: ")
        response = self.client.post("fir", {
            "state": state,
            "district": district,
            "police_station": police_station,
            "fir_number": fir_number,
            "year": year,
            "status": status
        })
        result = pretty_print(response)
        print(result)

    def party_search(self):
        party_name = input("Enter Petitioner vs Respondent Name: ")
        status = input("Enter Status: ")
        response = self.client.post("party", {
            "petitioner_respondent": party_name,
            "status": status
        })
        result = pretty_print(response)
        print(result)

    def subordinate_search(self):
        state = input("Enter State: ")
        district = input("Enter District: ")
        court_name = input("Enter Subordinate Court Name: ")
        judge_name = input("Enter Judge Name: ")
        response = self.client.post("subordinate", {
            "state": state,
            "district": district,
            "subordinate_court_name": court_name,
            "judge_name": judge_name
        })
        result = pretty_print(response)
        print(result)

    def advocate_search(self):
        advocate_name = input("Enter Advocate Name: ")
        status = input("Enter Status: ")
        response = self.client.post("advocate", {
            "advocate_name": advocate_name,
            "status": status
        })
        result = pretty_print(response)
        print(result)

    def cause_list_search(self):
        court_name = input("Enter Court Name: ")
        court_type = input("Enter Court Type: ")
        response = self.client.post("cause_list", {
            "court_name": court_name,
            "court_type": court_type
        })
        result = pretty_print(response)
        print(result)

    def lokadalat_search(self):
        status = input("Enter Status: ")
        lokadalat = input("Lok Adalat (Yes/No): ")
        panel = input("Enter Panel Name: ")
        response = self.client.post("lokadalat", {
            "status": status,
            "lokadalat": lokadalat,
            "panel": panel
        })
        result = pretty_print(response)
        print(result)

    def caveat_search(self):
        caveat_type = input("Enter Caveat Type: ")
        caveator_name = input("Enter Caveator Name: ")
        caveatee_name = input("Enter Caveatee Name: ")
        response = self.client.post("caveat", {
            "caveat_type": caveat_type,
            "caveator_name": caveator_name,
            "caveatee_name": caveatee_name
        })
        result = pretty_print(response)
        print(result)

    def pre_panel_search(self):
        police_station = input("Enter Police Station: ")
        fir_type = input("Enter FIR Type (e.g., IPC 420/506): ")
        fir_number = input("Enter FIR Number: ")
        year = input("Enter Year: ")
        response = self.client.post("pre_panel", {
            "police_station": police_station,
            "fir_type": fir_type,
            "fir_number": fir_number,
            "year": year
        })
        result = pretty_print(response)
        print(result)


# ----------------- Main Runner -----------------
if __name__ == "__main__":
    APITestManager().run()

