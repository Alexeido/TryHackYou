import { ImageResponse } from 'next/og';

// Configuración de la imagen
export const size = {
    width: 32,
    height: 32,
};
export const contentType = 'image/png';

// Generación del Favicon con código
export default function Icon() {
    return new ImageResponse(
        (
            <div
                style={{
                    fontSize: 28, // Aumenta el tamaño del #
                    background: 'black',
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#4ade80',
                    borderRadius: '30%',
                    border: '1px solid #22c55e',
                }}
            >
                #
            </div>
        ),
        { ...size }
    );
}
