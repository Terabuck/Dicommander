from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import pydicom
from PIL import Image
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

def dicom_to_thumbnail(dicom_path):
    ds = pydicom.dcmread(dicom_path)
    pixel_array = ds.pixel_array
    
    # Normalizar los valores de píxeles a 8 bits
    pixel_array = (pixel_array / pixel_array.max()) * 255
    pixel_array = pixel_array.astype(np.uint8)
    
    image = Image.fromarray(pixel_array)
    
    # Convertir la imagen a modo 'L' (escala de grises) si no está en un modo compatible
    if image.mode not in ('L', 'RGB'):
        image = image.convert('L')
    
    thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(dicom_path).replace('.dcm', '.jpg'))
    image.thumbnail((200, 200))
    image.save(thumbnail_path)
    return thumbnail_path

def get_dicom_tags(dicom_path):
    ds = pydicom.dcmread(dicom_path)
    laterality = ds.get((0x0020, 0x0062), 'Unknown').value
    view_position = ds.get((0x0018, 0x5101), 'Unknown').value
    return laterality, view_position

def format_dicom_tags(laterality, view_position):
    return f"{laterality}-{view_position}"

def crop_dicom_image(dicom_path, x, y, width, height):
    try:
        ds = pydicom.dcmread(dicom_path)
        pixel_array = ds.pixel_array
        
        # Aplicar el recorte
        cropped_pixel_array = pixel_array[y:y+height, x:x+width]
        
        # Actualizar el pixel array en el dataset DICOM
        ds.PixelData = cropped_pixel_array.tobytes()
        ds.Rows, ds.Columns = cropped_pixel_array.shape
        
        # Sobrescribir la imagen DICOM original con la recortada
        ds.save_as(dicom_path)
        
        # Generar un nuevo thumbnail
        dicom_to_thumbnail(dicom_path)
        
        return dicom_path
    except Exception as e:
        print(f"Error cropping DICOM image: {e}")
        return None

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            files = request.files.getlist('files')
            print(f"Received files: {files}")
            for file in files[:4]:
                if file and file.filename.endswith('.dcm'):
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(file.filename))
                    print(f"Saving file to: {file_path}")
                    file.save(file_path)
                    dicom_to_thumbnail(file_path)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Error: {e}")
            return "An error occurred while processing the files.", 500
    thumbnails = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith('.jpg'):
            dicom_path = filename.replace('.jpg', '.dcm')
            dicom_full_path = os.path.join(app.config['UPLOAD_FOLDER'], dicom_path)
            laterality, view_position = get_dicom_tags(dicom_full_path)
            formatted_tags = format_dicom_tags(laterality, view_position)
            thumbnails.append({
                'filename': filename,
                'formatted_tags': formatted_tags
            })
    
    # Ordenar las imágenes en el orden especificado
    order = ['R-CC', 'L-CC', 'R-MLO', 'L-MLO']
    thumbnails.sort(key=lambda x: order.index(x['formatted_tags']) if x['formatted_tags'] in order else len(order))
    
    print(f"Thumbnails: {thumbnails}")
    return render_template('index.html', thumbnails=thumbnails)

@app.route('/crop', methods=['POST'])
def crop():
    try:
        data = request.json
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], data['filename'])
        dicom_path = image_path.replace('.jpg', '.dcm')
        x = data['x']
        y = data['y']
        width = data['width']
        height = data['height']
        print(f"Cropping image: {dicom_path} at ({x}, {y}, {width}, {height})")
        cropped_dicom_path = crop_dicom_image(dicom_path, x, y, width, height)
        if cropped_dicom_path:
            cropped_image_path = cropped_dicom_path.replace('.dcm', '.jpg')
            return jsonify({'cropped_image_path': cropped_image_path})
        else:
            return jsonify({'error': 'Failed to crop DICOM image'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
