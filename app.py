from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import pydicom
from PIL import Image, ImageDraw
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
    laterality = ds.get((0x0020, 0x0062), 'Unknown')
    view_position = ds.get((0x0018, 0x5101), 'Unknown')
    if isinstance(laterality, pydicom.dataelem.DataElement):
        laterality = laterality.value
    if isinstance(view_position, pydicom.dataelem.DataElement):
        view_position = view_position.value
    return laterality, view_position

def format_dicom_tags(laterality, view_position):
    return f"{laterality}-{view_position}"

def crop_dicom_image(dicom_path, x, y, width, height):
    try:
        ds = pydicom.dcmread(dicom_path)
        pixel_array = ds.pixel_array
        
        # Ensure coordinates are within valid range
        x = max(0, x)
        y = max(0, y)
        width = min(ds.Columns - x, width)
        height = min(ds.Rows - y, height)
        
        # Aplicar el recorte
        cropped_pixel_array = pixel_array[y:y+height, x:x+width]
        
        # Actualizar el pixel array en el dataset DICOM
        ds.PixelData = cropped_pixel_array.tobytes()
        ds.Rows, ds.Columns = cropped_pixel_array.shape
        
        # Guardar la imagen DICOM recortada
        cropped_dicom_path = dicom_path.replace('.dcm', '_cropped.dcm')
        ds.save_as(cropped_dicom_path)
        
        # Generar un nuevo thumbnail
        dicom_to_thumbnail(cropped_dicom_path)
        
        return cropped_dicom_path
    except Exception as e:
        print(f"Error cropping DICOM image: {e}")
        return None

def crop_dicom_polygon(dicom_path, points):
    try:
        ds = pydicom.dcmread(dicom_path)
        pixel_array = ds.pixel_array
        
        # Ensure coordinates are tuples and handle negative coordinates
        points = [(max(0, int(point['x'])), max(0, int(point['y']))) for point in points]
        
        # Create a mask for the polygon
        mask = Image.new('L', (ds.Columns, ds.Rows), 0)
        ImageDraw.Draw(mask).polygon(points, outline=1, fill=1)
        mask = np.array(mask)
        
        # Apply the mask to the pixel array
        pixel_array[mask == 0] = 0
        
        # Update the pixel array in the DICOM dataset
        ds.PixelData = pixel_array.tobytes()
        
        # Guardar la imagen DICOM recortada
        cropped_dicom_path = dicom_path.replace('.dcm', '_cropped.dcm')
        ds.save_as(cropped_dicom_path)
        
        # Generar un nuevo thumbnail
        dicom_to_thumbnail(cropped_dicom_path)
        
        return cropped_dicom_path
    except Exception as e:
        print(f"Error cropping DICOM image: {e}")
        return None

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/dicom-dimensions')
def dicom_dimensions():
    filename = request.args.get('filename')
    dicom_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.replace('.jpg', '.dcm'))
    ds = pydicom.dcmread(dicom_path)
    return jsonify({'width': ds.Columns, 'height': ds.Rows})

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
        if 'points' in data:
            points = data['points']
            print(f"Cropping image with polygon: {points}")
            cropped_dicom_path = crop_dicom_polygon(dicom_path, points)
        else:
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
