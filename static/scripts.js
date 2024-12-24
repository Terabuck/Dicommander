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

document.getElementById('start-over-form').addEventListener('submit', function(event) {
    event.preventDefault();
    if (confirm('Are you sure you want to delete all files?')) {
        fetch('/start-over', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Failed to delete files.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while deleting files.');
        });
    }
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
let rectX, rectY, rectWidth, rectHeight;
let polygonPoints = [];
let cropMode = 'rectangle';
let dicomWidth, dicomHeight;

const cropCanvas = document.getElementById('crop-canvas');
const ctx = cropCanvas.getContext('2d');

document.querySelectorAll('input[name="crop-mode"]').forEach((input) => {
    input.addEventListener('change', function(event) {
        cropMode = event.target.value;
        ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
        polygonPoints = [];
    });
});

cropCanvas.addEventListener('mousedown', function(event) {
    if (cropMode === 'rectangle') {
        isDrawing = true;
        startX = event.offsetX;
        startY = event.offsetY;
    } else if (cropMode === 'polygon') {
        polygonPoints.push({ x: event.offsetX, y: event.offsetY });
        if (polygonPoints.length > 1) {
            ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
            ctx.beginPath();
            ctx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
            for (let i = 1; i < polygonPoints.length; i++) {
                ctx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
            }
            ctx.closePath();
            ctx.strokeStyle = 'lightgreen'; // Set the stroke color to light green
            ctx.stroke();
        }
    }
});

cropCanvas.addEventListener('mousemove', function(event) {
    if (isDrawing && cropMode === 'rectangle') {
        const currentX = event.offsetX;
        const currentY = event.offsetY;
        ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
        rectX = Math.min(startX, currentX);
        rectY = Math.min(startY, currentY);
        rectWidth = Math.abs(currentX - startX);
        rectHeight = Math.abs(currentY - startY);
        ctx.strokeStyle = 'lightgreen'; // Set the stroke color to light green
        ctx.strokeRect(rectX, rectY, rectWidth, rectHeight);
    }
});

cropCanvas.addEventListener('mouseup', function(event) {
    if (isDrawing && cropMode === 'rectangle') {
        isDrawing = false;
        console.log(`Selected area: (${rectX}, ${rectY}) to (${rectX + rectWidth}, ${rectY + rectHeight})`);
        previewCrop(rectX, rectY, rectWidth, rectHeight);
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

function fetchDicomDimensions(filename) {
    return fetch(`/dicom-dimensions?filename=${filename}`)
        .then(response => response.json())
        .then(data => {
            dicomWidth = data.width;
            dicomHeight = data.height;
        })
        .catch(error => {
            console.error('Error fetching DICOM dimensions:', error);
        });
}

function cropImage() {
    const selectedImage = document.getElementById('selected-image');
    const filename = selectedImage.src.split('/').pop();

    fetchDicomDimensions(filename).then(() => {
        if (cropMode === 'rectangle') {
            // Scale the coordinates of the crop area
            const scaledX = Math.max(0, Math.round(rectX * dicomWidth / selectedImage.width));
            const scaledY = Math.max(0, Math.round(rectY * dicomHeight / selectedImage.height));
            const scaledWidth = Math.min(dicomWidth - scaledX, Math.round(rectWidth * dicomWidth / selectedImage.width));
            const scaledHeight = Math.min(dicomHeight - scaledY, Math.round(rectHeight * dicomHeight / selectedImage.height));

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
        } else if (cropMode === 'polygon') {
            // Scale the polygon points
            const scaledPoints = polygonPoints.map(point => ({
                x: Math.max(0, Math.round(point.x * dicomWidth / selectedImage.width)),
                y: Math.max(0, Math.round(point.y * dicomHeight / selectedImage.height))
            }));

            console.log('Scaled polygon points:', scaledPoints);

            fetch('/crop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filename: filename,
                    points: scaledPoints
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
    });
}

document.getElementById('center-image-button').addEventListener('click', cropImage);