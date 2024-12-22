document.getElementById('upload-form').addEventListener('submit', function(event) {
    event.preventDefault();
    const folderInput = document.getElementById('folder-input');
    const files = folderInput.files;
    const formData = new FormData();

    for (let i = 0; i < files.length && i < 4; i++) {
        formData.append('files', files[i]);
    }

    console.log('FormData:', formData);

    fetch('/', {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(data => {
        console.log(data);
        window.location.reload();
    })
    .catch(error => {
        console.error('Error:', error);
    });
});

function showImage(src) {
    const selectedImage = document.getElementById('selected-image');
    selectedImage.src = src;
    const cropCanvas = document.getElementById('crop-canvas');
    cropCanvas.width = selectedImage.naturalWidth;
    cropCanvas.height = selectedImage.naturalHeight;
    cropCanvas.style.width = selectedImage.width + 'px';
    cropCanvas.style.height = selectedImage.height + 'px';
}

let isDrawing = false;
let startX, startY;

const cropCanvas = document.getElementById('crop-canvas');
const ctx = cropCanvas.getContext('2d');

cropCanvas.addEventListener('mousedown', function(event) {
    isDrawing = true;
    startX = event.offsetX;
    startY = event.offsetY;
});

cropCanvas.addEventListener('mousemove', function(event) {
    if (isDrawing) {
        const currentX = event.offsetX;
        const currentY = event.offsetY;
        ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
        ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
    }
});

cropCanvas.addEventListener('mouseup', function(event) {
    if (isDrawing) {
        isDrawing = false;
        const endX = event.offsetX;
        const endY = event.offsetY;
        const rectX = Math.min(startX, endX);
        const rectY = Math.min(startY, endY);
        const rectWidth = Math.abs(endX - startX);
        const rectHeight = Math.abs(endY - startY);
        console.log(`Selected area: (${rectX}, ${rectY}) to (${rectX + rectWidth}, ${rectY + rectHeight})`);
        previewCrop(rectX, rectY, rectWidth, rectHeight);
        cropImage(rectX, rectY, rectWidth, rectHeight);
    }
});

function previewCrop(x, y, width, height) {
    const selectedImage = document.getElementById('selected-image');
    const previewCanvas = document.getElementById('preview-canvas');
    if (previewCanvas) {
        const previewCtx = previewCanvas.getContext('2d');
        previewCanvas.width = width;
        previewCanvas.height = height;
        previewCtx.drawImage(selectedImage, x, y, width, height, 0, 0, width, height);
    } else {
        console.error('preview-canvas not found');
    }
}

function cropImage(x, y, width, height) {
    const selectedImage = document.getElementById('selected-image');
    const filename = selectedImage.src.split('/').pop();
    const originalWidth = 2736; // Ancho original de la imagen DICOM
    const originalHeight = 3584; // Alto original de la imagen DICOM
    const thumbnailWidth = selectedImage.naturalWidth;
    const thumbnailHeight = selectedImage.naturalHeight;

    // Escalar las coordenadas del área de recorte
    const scaledX = Math.round(x * originalWidth / thumbnailWidth);
    const scaledY = Math.round(y * originalHeight / thumbnailHeight);
    const scaledWidth = Math.round(width * originalWidth / thumbnailWidth);
    const scaledHeight = Math.round(height * originalHeight / thumbnailHeight);

    console.log(`Scaled area: (${scaledX}, ${scaledY}) to (${scaledX + scaledWidth}, ${scaledY + scaledHeight})`);

    fetch('/crop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            filename: filename,
            x: scaledX,
            y: scaledY,
            width: scaledWidth,
            height: scaledHeight
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.cropped_image_path) {
            console.log('Cropped image path:', data.cropped_image_path);
            selectedImage.src = data.cropped_image_path;
        } else {
            console.error('Error cropping image:', data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function centerImage() {
    const selectedImage = document.getElementById('selected-image');
    // Aquí puedes añadir la lógica para centrar la imagen
    console.log('Centrar imagen:', selectedImage.src);
}
