'''
Maria Freixas Solé 
Este archivo tiene las funciones necesarias para trabajar con los canales de una señal estéreo
y convertirla (o devolverla) a formato mono, para que sea compatible con sistemas que solo usan
un canal de audio.
'''

import struct

def crear_cabecera(canales, frec_muestreo, bits_muestra, tam_datos):
    """
    Crea la cabecera WAVE con los parámetros dados.
    Devuelve la cabecera empaquetada como bytes.
    """
    tasa_bytes = frec_muestreo * canales * bits_muestra // 8
    bloque = canales * bits_muestra // 8
    tam_riff = 36 + tam_datos
    return (
        struct.pack('4sI4s', b'RIFF', tam_riff, b'WAVE') +
        struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, canales,
                    frec_muestreo, tasa_bytes, bloque, bits_muestra) +
        struct.pack('<4sI', b'data', tam_datos)
    )

def leer_cabecera(fichero):
    """
    Lee y extrae los metadatos de la cabecera WAVE.
    Devuelve un diccionario con la información del audio.
    """
    fichero.seek(0)
    cab_riff, _, tipo_wave = struct.unpack('<4sI4s', fichero.read(12))
    if cab_riff != b'RIFF' or tipo_wave != b'WAVE':
        raise TypeError('El archivo no es un WAVE válido')
    
    info_audio = {
        'despl_datos': None,
        'tam_datos': None,
        'formato': None,
        'canales': None,
        'frec_muestreo': None,
        'bits_muestra': None
    }

    while True:
        cab = fichero.read(8)
        if len(cab) < 8:
            break
        ident, tam = struct.unpack('<4sI', cab)
        if ident == b'fmt ':
            datos_fmt = fichero.read(tam)
            info_audio['formato'], info_audio['canales'], info_audio['frec_muestreo'], _, _, info_audio['bits_muestra'] = struct.unpack('<HHIIHH', datos_fmt[:16])
        elif ident == b'data':
            info_audio['despl_datos'] = fichero.tell()
            info_audio['tam_datos'] = tam
            fichero.seek(tam, 1)
        else:
            fichero.seek(tam, 1)
    
    if info_audio['formato'] != 1 or info_audio['bits_muestra'] not in (16, 32):
        raise TypeError("Formato de audio no compatible")
    
    return info_audio

def estereo2mono(fic_estereo, fic_salida, canal=2):
    '''
    Convierte un archivo estéreo a mono.
    canal = 0: izquierdo, 1: derecho, 2: semisuma, 3: semidiferencia
    '''
    with open(fic_estereo, 'rb') as f_est:
        info = leer_cabecera(f_est)
        if info['canales'] != 2:
            raise TypeError("El archivo no es estéreo")
        f_est.seek(info['despl_datos'])
        datos = f_est.read(info['tam_datos'])

    muestras = struct.unpack('<' + 'h' * (info['tam_datos'] // 2), datos)
    pares = zip(muestras[::2], muestras[1::2])

    if canal == 0:
        mono = [izq for izq, _ in pares]
    elif canal == 1:
        mono = [der for _, der in pares]
    elif canal == 2:
        mono = [(izq + der) // 2 for izq, der in pares]
    elif canal == 3:
        mono = [(izq - der) // 2 for izq, der in pares]
    else:
        raise TypeError('Canal no válido')

    datos_mono = struct.pack('<' + 'h' * len(mono), *mono)

    with open(fic_salida, 'wb') as f_out:
        f_out.write(crear_cabecera(1, info['frec_muestreo'], 16, len(datos_mono)))
        f_out.write(datos_mono)

def mono2estereo(fic_izq, fic_der, fic_salida):
    '''
    Une dos archivos mono (izquierdo y derecho) en un archivo estéreo.
    '''
    with open(fic_izq, 'rb') as f_izq:
        info_izq = leer_cabecera(f_izq)
        if info_izq['canales'] != 1:
            raise TypeError("El canal izquierdo no es mono")
        f_izq.seek(info_izq['despl_datos'])
        datos_izq = struct.unpack('<' + 'h' * (info_izq['tam_datos'] // 2), f_izq.read(info_izq['tam_datos']))

    with open(fic_der, 'rb') as f_der:
        info_der = leer_cabecera(f_der)
        if info_der['canales'] != 1:
            raise TypeError("El canal derecho no es mono")
        f_der.seek(info_der['despl_datos'])
        datos_der = struct.unpack('<' + 'h' * (info_der['tam_datos'] // 2), f_der.read(info_der['tam_datos']))

    datos_est = struct.pack('<' + 'h' * (2 * len(datos_izq)), *sum(zip(datos_izq, datos_der), ()))

    with open(fic_salida, 'wb') as f_out:
        f_out.write(crear_cabecera(2, info_izq['frec_muestreo'], 16, len(datos_est)))
        f_out.write(datos_est)

def codEstereo(fic_entrada, fic_codificado):
    '''
    Codifica una señal estéreo (16 bits por canal) en una sola señal de 32 bits.
    '''
    with open(fic_entrada, 'rb') as f:
        info = leer_cabecera(f)
        if info['canales'] != 2:
            raise TypeError("El archivo no es estéreo")
        f.seek(info['despl_datos'])
        datos = struct.unpack('<' + 'h' * (info['tam_datos'] // 2), f.read(info['tam_datos']))

    pares = zip(datos[::2], datos[1::2])
    codificados = [((l + r) << 16 & 0xFFFF0000) | ((l - r) & 0xFFFF) for l, r in pares]

    datos_cod = struct.pack('<' + 'I' * len(codificados), *codificados)

    with open(fic_codificado, 'wb') as f_out:
        f_out.write(crear_cabecera(1, info['frec_muestreo'], 32, len(datos_cod)))
        f_out.write(datos_cod)

def decEstereo(fic_codificado, fic_salida):
    '''
    Decodifica una señal monofónica de 32 bits en una señal estéreo original.
    '''
    with open(fic_codificado, 'rb') as f:
        info = leer_cabecera(f)
        if info['bits_muestra'] != 32:
            raise TypeError('La señal no está codificada en 32 bits')
        f.seek(info['despl_datos'])
        datos = struct.unpack('<' + 'I' * (info['tam_datos'] // 4), f.read(info['tam_datos']))

    reconstruido = []

    for cod in datos:
        suma = (cod >> 16) & 0xFFFF
        dif = cod & 0xFFFF
        suma = struct.unpack('<h', struct.pack('<H', suma))[0]
        dif = struct.unpack('<h', struct.pack('<H', dif))[0]
        izq = (suma + dif) // 2
        der = (suma - dif) // 2
        reconstruido.append(izq)
        reconstruido.append(der)

    datos_est = struct.pack('<' + 'h' * len(reconstruido), *reconstruido)

    with open(fic_salida, 'wb') as f_out:
        f_out.write(crear_cabecera(2, info['frec_muestreo'], 16, len(datos_est)))
        f_out.write(datos_est)
