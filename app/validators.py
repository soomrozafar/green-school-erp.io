import re

def clean_phone(value):
    v=(value or "").strip()
    if not v: return ""
    digits=re.sub(r"[\s()\-]", "", v)
    if digits.startswith("+"): digits="+"+re.sub(r"\D", "", digits[1:])
    else: digits=re.sub(r"\D", "", digits)
    if len(digits.replace("+", "")) < 7 or len(digits.replace("+", "")) > 15: raise ValueError("Invalid phone/mobile number")
    return digits

def clean_cnic(value):
    v=(value or "").strip()
    if not v: return ""
    digits=re.sub(r"\D", "", v)
    if len(digits)!=13: raise ValueError("CNIC must contain 13 digits")
    return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"


def whatsapp_number(value):
    raw = (value or "").strip()
    if not re.fullmatch(r"\+?[0-9\s().-]+", raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if re.fullmatch(r"03[0-9]{9}", digits):
        return "92" + digits[1:]
    if re.fullmatch(r"923[0-9]{9}", digits):
        return digits
    if digits.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+"):
        return None
    return digits if re.fullmatch(r"[1-9][0-9]{7,14}", digits) else None
