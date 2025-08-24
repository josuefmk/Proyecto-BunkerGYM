import re
def validar_rut(rut: str) -> bool:
    try:
        rut = rut.upper().strip()


        if "." in rut:
            return False

        if not re.match(r'^\d{7,8}-[\dK]$', rut):
            return False

        num, dv = rut.split('-')
        suma = 0
        multiplicador = 2

        for digito in reversed(num):
            suma += int(digito) * multiplicador
            multiplicador += 1
            if multiplicador > 7:
                multiplicador = 2

        resto = suma % 11
        dv_calculado = 11 - resto

        if dv_calculado == 11:
            dv_calculado = '0'
        elif dv_calculado == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(dv_calculado)

        return dv == dv_calculado
    except:
        return False


def validar_correo(correo: str) -> bool:
    """Valida formato básico de correo."""
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', correo) is not None


def validar_telefono(telefono: str) -> bool:
    """Valida teléfono chileno (+56 9 XXXXXXXX o 9 dígitos)."""
    telefono = telefono.strip().replace(" ", "").replace("-", "")
    return re.match(r'^(?:\+?56)?9\d{8}$', telefono) is not None
