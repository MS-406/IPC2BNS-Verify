import re
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

@dataclass
class ExtractedTimeline:
    raw_query: str
    incident_date: Optional[date] = None
    fir_date: Optional[date] = None
    petition_date: Optional[date] = None
    appeal_date: Optional[date] = None
    trial_start_date: Optional[date] = None
    judgment_date: Optional[date] = None
    posture: str = "UNKNOWN"
    jurisdiction_hint: Optional[str] = None
    extracted_dates: List[Dict[str, Any]] = field(default_factory=list)

class TimelineParser:
    """
    Parses temporal information, procedural postures, and dates from legal queries.
    """
    CUTOFF_DATE = date(2024, 7, 1)

    def __init__(self):
        # Regex patterns for date extraction
        self.date_patterns = [
            # ISO: 2024-06-20
            re.compile(r'\b(?P<year>19\d\d|20\d\d)-(?P<month>0?[1-9]|1[0-2])-(?P<day>0?[1-9]|[12]\d|3[01])\b'),
            # DD/MM/YYYY or DD-MM-YYYY
            re.compile(r'\b(?P<day>0?[1-9]|[12]\d|3[01])[/\-\.](?P<month>0?[1-9]|1[0-2])[/\-\.](?P<year>19\d\d|20\d\d)\b'),
            # Month DD, YYYY e.g. June 20, 2024 or 20th June 2024
            re.compile(r'\b(?P<month_name>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(?P<day>[0-3]?\d)(?:st|nd|rd|th)?,?\s+(?P<year>19\d\d|20\d\d)\b', re.IGNORECASE),
            re.compile(r'\b(?P<day>[0-3]?\d)(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<month_name>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec),?\s+(?P<year>19\d\d|20\d\d)\b', re.IGNORECASE),
            # Just Month YYYY (e.g. May 2024 -> default to 15th of that month)
            re.compile(r'\b(?P<month_name>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(?P<year>19\d\d|20\d\d)\b', re.IGNORECASE)
        ]

        # Posture keywords mapping
        self.posture_keywords = {
            "APPEAL_OR_REVISION": ["appeal", "appellate", "revision", "quashing", "482 crpc", "528 bnss", "high court petition", "special leave", "challenging", "challenge", "impugned"],
            "BAIL_APPLICATION": ["anticipatory bail", "regular bail", "bail application", "section 438", "section 439", "section 482 bnss", "section 483 bnss", "bail"],
            "TRIAL_ONGOING": ["trial", "cognizance", "charge framed", "witness examination", "sessions case", "magistrate trial", "conviction", "judgment"],
            "CHARGE_SHEET_FILED": ["chargesheet", "charge sheet", "final report", "173 crpc", "193 bnss"],
            "INVESTIGATION_PENDING": ["investigation", "inquiry", "investigating officer", "remand", "custody"],
            "FIR_REGISTERED": ["fir", "first information report", "police complaint", "lodged complaint", "crime registered"],
            "INCIDENT_ONLY": ["incident", "offence committed", "crime occurred", "act committed", "happened on", "occurred on"]
        }


        # Jurisdictions
        self.jurisdictions = {
            "Kerala": ["kerala", "ker hc", "kerala high court"],
            "Punjab_and_Haryana": ["punjab", "haryana", "chandigarh", "p&h", "p&h hc", "punjab and haryana"],
            "Delhi": ["delhi", "dhc", "delhi high court"],
            "Bombay": ["bombay", "maharashtra", "mumbai", "bhc", "bombay high court", "nagpur"],
            "Allahabad": ["allahabad", "uttar pradesh", "up hc", "allahabad high court"],
            "Rajasthan": ["rajasthan", "jaipur", "jodhpur", "rajasthan high court"],
            "Karnataka": ["karnataka", "bengaluru", "bangalore", "karnataka high court"],
            "Madras": ["madras", "tamil nadu", "chennai", "madras high court"]
        }

    def _parse_match_to_date(self, m: re.Match) -> Optional[date]:
        d = m.groupdict()
        year = int(d.get("year"))
        month = None
        day = 15 # default mid-month if day missing

        if "month" in d and d["month"]:
            month = int(d["month"])
        elif "month_name" in d and d["month_name"]:
            month = MONTH_MAP.get(d["month_name"].lower())

        if "day" in d and d["day"]:
            day = int(d["day"])

        if month and 1 <= month <= 12 and 1 <= day <= 31:
            try:
                return date(year, month, day)
            except ValueError:
                return date(year, month, min(day, 28))
        return None

    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        extracted = []
        for pat in self.date_patterns:
            for match in pat.finditer(text):
                parsed = self._parse_match_to_date(match)
                if parsed:
                    extracted.append({
                        "date": parsed,
                        "raw_str": match.group(0),
                        "start": match.start(),
                        "end": match.end()
                    })

        # Sort by match length descending to keep longer specific dates (e.g. '10 March 2024' over 'March 2024')
        extracted = sorted(extracted, key=lambda x: (x["end"] - x["start"]), reverse=True)
        non_overlapping = []
        occupied_spans = []

        for item in extracted:
            s, e = item["start"], item["end"]
            # Check if this span overlaps with an already accepted longer span
            if not any(max(s, occ_s) < min(e, occ_e) for occ_s, occ_e in occupied_spans):
                non_overlapping.append(item)
                occupied_spans.append((s, e))

        # Sort chronologically by appearance in text
        return sorted(non_overlapping, key=lambda x: x["start"])


    def detect_posture(self, text: str) -> str:
        text_lower = text.lower()
        for posture, keywords in self.posture_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return posture
        return "INCIDENT_ONLY"

    def detect_jurisdiction(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for jur, keywords in self.jurisdictions.items():
            for kw in keywords:
                if kw in text_lower:
                    return jur
        return None

    def _find_context_role(self, text: str, start: int, end: int) -> str:
        """Looks at immediate preceding and surrounding text to identify date role."""
        # Prioritize immediate preceding context (up to 30 chars before date)
        preceding = text[max(0, start - 30):start].lower()
        if any(k in preceding for k in ["appeal", "revision", "quashing", "appellate"]):
            return "appeal_date"
        if any(k in preceding for k in ["bail", "anticipatory", "petition", "filed on", "filing"]):
            return "petition_date"
        if any(k in preceding for k in ["fir", "complaint", "lodged", "registered"]):
            return "fir_date"
        if any(k in preceding for k in ["conviction", "judgment", "order"]):
            return "judgment_date"
        if any(k in preceding for k in ["incident", "occurred", "happened", "assault", "theft", "crime", "offence", "act", "statement", "defamation", "fraud", "made on"]):
            return "incident_date"


        # Surrounding context fallback (window of 20 chars around)
        window = text[max(0, start - 20):min(len(text), end + 20)].lower()
        if any(k in window for k in ["appeal", "revision"]):
            return "appeal_date"
        if any(k in window for k in ["bail", "petition"]):
            return "petition_date"
        if any(k in window for k in ["fir", "lodged", "complaint"]):
            return "fir_date"
        if any(k in window for k in ["incident", "happened", "occurred"]):
            return "incident_date"

        return "unknown"


    def parse(self, query: str) -> ExtractedTimeline:
        extracted_dates = self.extract_dates(query)
        posture = self.detect_posture(query)
        jurisdiction = self.detect_jurisdiction(query)

        timeline = ExtractedTimeline(
            raw_query=query,
            posture=posture,
            jurisdiction_hint=jurisdiction,
            extracted_dates=extracted_dates
        )

        query_lower = query.lower()

        # Context-aware date binding
        for item in extracted_dates:
            d = item["date"]
            role = self._find_context_role(query, item["start"], item["end"])
            if role == "appeal_date":
                timeline.appeal_date = d
            elif role == "petition_date":
                timeline.petition_date = d
            elif role == "fir_date":
                timeline.fir_date = d
            elif role == "judgment_date":
                timeline.judgment_date = d
                if timeline.incident_date is None:
                    timeline.incident_date = d
            elif role == "incident_date":
                timeline.incident_date = d

        # Fallback bindings if roles couldn't be definitively separated
        if extracted_dates:
            sorted_dates = sorted([x["date"] for x in extracted_dates])
            earliest = sorted_dates[0]
            latest = sorted_dates[-1]

            if timeline.incident_date is None:
                timeline.incident_date = earliest

            if len(sorted_dates) > 1:
                if posture in ["APPEAL_OR_REVISION"] and timeline.appeal_date is None:
                    timeline.appeal_date = latest
                elif posture in ["BAIL_APPLICATION"] and timeline.petition_date is None:
                    timeline.petition_date = latest
                elif posture in ["FIR_REGISTERED", "INVESTIGATION_PENDING"] and timeline.fir_date is None:
                    timeline.fir_date = latest

        # Default fallback if no date found: look for relative terms
        if not extracted_dates:
            if "pre-july" in query_lower or "before july 2024" in query_lower or "june 2024" in query_lower:
                timeline.incident_date = date(2024, 6, 15)
            elif "post-july" in query_lower or "after july 2024" in query_lower or "august 2024" in query_lower:
                timeline.incident_date = date(2024, 8, 15)

        return timeline

