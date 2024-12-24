from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
import os
import pydicom
from pydicom.uid import generate_uid
from PIL import Image, ImageDraw
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'

def apply_window_level(pixel_array, window_center, window_width):
    # Calculate the minimum and maximum values for the window
    min_val = window_center - (window_width / 2)
    max_val = window_center + (window_width / 2)
    
    # Clip the pixel values to the window range
    pixel_array = np.clip(pixel_array, min_val, max_val)
    
    # Normalize the pixel values to the range 0-255
    pixel_array = (pixel_array - min_val) / (max_val - min_val) * 255
    
    # Convert the pixel array to uint8 type
    return pixel_array.astype(np.uint8)

def dicom_to_thumbnail(dicom_path):
    # Read the DICOM file
    ds = pydicom.dcmread(dicom_path)
    pixel_array = ds.pixel_array
    
    # Apply window width and window level
    window_center = ds.WindowCenter if 'WindowCenter' in ds else np.mean(pixel_array)
    window_width = ds.WindowWidth if 'WindowWidth' in ds else np.max(pixel_array) - np.min(pixel_array)
    if isinstance(window_center, pydicom.multival.MultiValue):
        window_center = window_center[0]
    if isinstance(window_width, pydicom.multival.MultiValue):
        window_width = window_width[0]
    pixel_array = apply_window_level(pixel_array, window_center, window_width)
    
    # Check if the image is inverted
    is_inverted = np.mean(pixel_array) > 127
    if is_inverted:
        pixel_array = 255 - pixel_array
    
    # Convert the pixel array to an image
    image = Image.fromarray(pixel_array)
    
    # Convert the image to 'L' mode (grayscale) if not already in a compatible mode
    if image.mode not in ('L', 'RGB'):
        image = image.convert('L')
    
    # Save the thumbnail image
    thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(dicom_path).replace('.dcm', '.jpg'))
    image.thumbnail((200, 200))
    image.save(thumbnail_path)
    return thumbnail_path, is_inverted

def get_dicom_tags(dicom_path):
    # Read the DICOM file
    ds = pydicom.dcmread(dicom_path)
    
    # Get the laterality and view position tags
    laterality = ds.get((0x0020, 0x0062), 'Unknown')
    view_position = ds.get((0x0018, 0x5101), 'Unknown')
    
    # Extract the values from the data elements if they exist
    if isinstance(laterality, pydicom.dataelem.DataElement):
        laterality = laterality.value
    if isinstance(view_position, pydicom.dataelem.DataElement):
        view_position = view_position.value
    
    return laterality, view_position

def format_dicom_tags(laterality, view_position):
    # Format the DICOM tags for display
    if laterality == 'Unknown' or view_position == 'Unknown':
        return 'Unknown'
    return f"{laterality}-{view_position}"

def crop_dicom_image(dicom_path, x, y, width, height):
    try:
        # Read the DICOM file
        ds = pydicom.dcmread(dicom_path)
        pixel_array = ds.pixel_array
        
        # Ensure coordinates are within valid range
        x = max(0, x)
        y = max(0, y)
        width = min(ds.Columns - x, width)
        height = min(ds.Rows - y, height)
        
        # Apply the crop
        cropped_pixel_array = pixel_array[y:y+height, x:x+width]
        
        # Update the pixel array in the DICOM dataset
        ds.PixelData = cropped_pixel_array.tobytes()
        ds.Rows, ds.Columns = cropped_pixel_array.shape
        
        # Save the cropped DICOM image
        cropped_dicom_path = dicom_path.replace('.dcm', '_cropped.dcm')
        ds.save_as(cropped_dicom_path)
        
        # Generate a new thumbnail
        dicom_to_thumbnail(cropped_dicom_path)
        
        return cropped_dicom_path
    except Exception as e:
        print(f"Error cropping DICOM image: {e}")
        return None

def crop_dicom_polygon(dicom_path, points):
    try:
        # Read the DICOM file
        ds = pydicom.dcmread(dicom_path)
        
        # Get the pixel array from the DICOM dataset
        pixel_array = ds.pixel_array
        
        # Check the photometric interpretation and convert if necessary
        # if ds.PhotometricInterpretation == 'MONOCHROME2':
        #    pixel_array = np.max(pixel_array) - pixel_array  # Invert the pixel values
        #    ds.PhotometricInterpretation = 'MONOCHROME1'  # Update the photometric interpretation
        
        # Ensure coordinates are tuples and handle negative coordinates
        points = [(max(0, int(point['x'])), max(0, int(point['y']))) for point in points]
        
        # Create a new image with mode 'L' (grayscale) and size of the DICOM image, initialized to 0 (black)
        mask = Image.new('L', (ds.Columns, ds.Rows), 0)

        # Draw the polygon on the mask with the given points, filling the inside with 1 (white)
        ImageDraw.Draw(mask).polygon(points, outline=0, fill=1)
                
        # Convert the mask to a NumPy array
        mask = np.array(mask)
        
        # Check if the image is inverted by calculating the mean pixel value
        is_inverted = np.mean(pixel_array) > 127
        
        # Fill the area outside the polygon with black or white based on the inversion flag. Check the photometric interpretation and convert if necessary
        if ds.PhotometricInterpretation == 'MONOCHROME2':
        # Apply the mask to the pixel array, setting pixels outside the polygon to 0
            pixel_array[mask == 0] = 0
        else:
            pixel_array[mask == 0] = -1
        
        # Save the cropped DICOM image
        cropped_dicom_path = dicom_path.replace('.dcm', '_cropped.dcm')
        ds.PixelData = pixel_array.tobytes()  # Update the pixel data in the DICOM dataset
        ds.save_as(cropped_dicom_path)
        
        # Generate a new thumbnail for the cropped DICOM image
        dicom_to_thumbnail(cropped_dicom_path)
        
        return cropped_dicom_path
    except Exception as e:
        # Print an error message if an exception occurs
        print(f"Error cropping DICOM image: {e}")
        return None

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Serve the uploaded file
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/dicom-dimensions')
def dicom_dimensions():
    # Get the DICOM file dimensions
    filename = request.args.get('filename')
    dicom_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.replace('.jpg', '.dcm'))
    ds = pydicom.dcmread(dicom_path)
    return jsonify({'width': ds.Columns, 'height': ds.Rows})

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Handle file uploads
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
    
    # Generate thumbnails for the uploaded DICOM files
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
    
    # Sort the thumbnails in the specified order
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
            # Generate a new InstanceUID for the cropped image
            ds = pydicom.dcmread(cropped_dicom_path)
            ds.SOPInstanceUID = generate_uid()
            ds.save_as(cropped_dicom_path)
            
            cropped_image_path = cropped_dicom_path.replace('.dcm', '.jpg')
            return jsonify({'cropped_image_path': cropped_image_path})
        else:
            return jsonify({'error': 'Failed to crop DICOM image'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/start-over', methods=['POST'])
def start_over():
    try:
        # Delete all files in the uploads folder
        folder = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)