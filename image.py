import IPython
import os
import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import requests
import urllib.parse
from io import BytesIO



def load_image(image, image_size=None, to_numpy=False, normalize=False):
    if isinstance(image, str):
        if is_url(image):
            image = url_to_image(image)
        elif os.path.exists(image):
            image = Image.open(image).convert('RGB')
        else:
            raise ValueError('no image found at %s'%image)
    elif isinstance(image, np.ndarray):
        image = Image.fromarray(image.astype(np.uint8)).convert('RGB')
    if image_size is not None and isinstance(image_size, tuple):
        image = resize(image, image_size)
    elif image_size is not None and not isinstance(image_size, tuple):
        aspect = get_aspect_ratio(image)
        image_size = (int(aspect * image_size), image_size)
        image = resize(image, image_size)
    if to_numpy:
        image = np.array(image)
        if normalize:
            image = image / 255.0        
    return image


def get_size(image):
    if isinstance(image, str):
        image = load_image(image, 1024)
        w, h = image.size
    elif isinstance(image, Image.Image):    
        w, h = image.size
    elif isinstance(image, np.ndarray):
        w, h = image.shape[1], image.shape[0]
    return w, h


def get_aspect_ratio(image):
    w, h = get_size(image)
    return float(w) / h


def resize(img, new_size, mode=None, align_corners=True):
    sampling_modes = {
        'nearest': Image.NEAREST, 
        'bilinear': Image.BILINEAR,
        'bicubic': Image.BICUBIC, 
        'lanczos': Image.LANCZOS
    }
    assert isinstance(new_size, tuple), \
        'Error: image_size must be a tuple.'
    assert mode is None or mode in sampling_modes.keys(), \
        'Error: resample mode %s not understood: options are nearest, bilinear, bicubic, lanczos.'
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img.astype(np.uint8)).convert('RGB')
    w1, h1 = img.size
    w2, h2 = new_size
    if (h1, w1) == (w2, h2):
        return img
    if mode is None:
        mode = 'bicubic' if w2*h2 >= w1*h1 else 'lanczos'
    resample_mode = sampling_modes[mode]
    return img.resize((w2, h2), resample=resample_mode)


def save(img, filename):
    folder = os.path.dirname(filename)
    if folder and not os.path.isdir(folder):
        os.mkdir(folder)
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img.astype(np.uint8)).convert('RGB')
    img.save(str(filename))

    
def display(img):
    if isinstance(img, list):
        return frames_to_movie(img, fps=30)
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img.astype(np.uint8)).convert('RGB')
    IPython.display.display(img)

    
def resize_tensor(image, image_size, mode='bicubic', align_corners=True):
    assert isinstance(image_size, tuple), 'Error: image_size must be a tuple'
    _, _, h1, w1 = image.shape
    if (w1, h1) == image_size:
        return image
    return torch.nn.functional.interpolate(
        image, 
        tuple(reversed(image_size)), 
        mode=mode, 
        align_corners=align_corners
    )


def random_tensor(w, h, c=3):
    tensor = torch.randn(c, h, w).mul(0.001).unsqueeze(0)
    return tensor


def random_tensor_like(base_image):
    w, h = base_image.size
    return random_tensor(w, h, 3)


def preprocess(image, image_size=None, to_normalize=True):
    if isinstance(image, str):
        image = Image.open(image).convert('RGB')
    if image_size is None:
        image_size = (image.height, image.width)
    elif type(image_size) is not tuple:
        image_size = tuple([int((float(image_size) / max(image.size)) * x) for x in (image.height, image.width)])
    Loader = transforms.Compose([transforms.Resize(image_size), transforms.ToTensor()])
    rgb2bgr = transforms.Compose([transforms.Lambda(lambda x: x[torch.LongTensor([2,1,0])])])
    if to_normalize:
        Normalize = transforms.Compose([transforms.Normalize(mean=[103.939, 116.779, 123.68], std=[1,1,1])])
        tensor = Normalize(rgb2bgr(Loader(image) * 256)).unsqueeze(0)
    else:
        tensor = rgb2bgr(Loader(image)).unsqueeze(0)
    return tensor


def deprocess(tensor):
    Normalize = transforms.Compose([transforms.Normalize(mean=[-103.939, -116.779, -123.68], std=[1,1,1])])
    bgr2rgb = transforms.Compose([transforms.Lambda(lambda x: x[torch.LongTensor([2,1,0])])])
    tensor = bgr2rgb(Normalize(tensor.squeeze(0).cpu())) / 256
    tensor.clamp_(0, 1)
    Image2PIL = transforms.ToPILImage()
    image = Image2PIL(tensor.cpu())
    return image


def original_colors(content, generated):
    #content, generated = deprocess(content.clone()), deprocess(generated.clone())    
    content_channels = list(content.convert('YCbCr').split())
    generated_channels = list(generated.convert('YCbCr').split())
    content_channels[0] = generated_channels[0]
    return Image.merge('YCbCr', content_channels).convert('RGB')


def url_to_image(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return img


def is_url(path):
    path = urllib.parse.urlparse(path)
    return path.netloc != ''
   