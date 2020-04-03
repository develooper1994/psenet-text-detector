import os
import cv2
import sys
import time
import collections
import torch
import argparse
import numpy as np
import params
import torchvision.transforms as transforms

from torch.autograd import Variable
from torch.utils import data

from Detection.PSEnet import models
from Detection.PSEnet import util
from Detection.PSEnet.pypse import pse as pypse
from PIL import Image

def scaleimg(img, long_size=2240):
    h, w = img.shape[0:2]
    scale = long_size * 1.0 / max(h, w)
    img = cv2.resize(img, dsize=None, fx=scale, fy=scale)
    return img

def crop(img,bbox):
    #img = cv2.imread(imgpath)
    bbox = bbox.reshape(4,2)
    topleft_x = np.min(bbox[:,0])
    topleft_y = np.min(bbox[:,1])
    bot_right_x = np.max(bbox[:,0])
    bot_right_y = np.max(bbox[:,1])
    cropped_img = img[topleft_y:bot_right_y, topleft_x:bot_right_x]
    cropped_img = cv2.resize(cropped_img,(100,32))
    cropped_img = cv2.cvtColor(cropped_img,cv2.COLOR_BGR2GRAY)
    cropped_img = Image.fromarray(cropped_img)
    #cropped_img = cropped_img.convert('RGB')
    cropped_img = transforms.ToTensor()(cropped_img)
    return cropped_img

def drawBBox(bboxs,img):
    for bbox in bboxs:
        bbox = np.reshape(bbox,(4,2))
        cv2.drawContours(img, [bbox],-1, (0, 255, 0), 2)
    cv2.imwrite('result.jpg',img)

def detect(org_img, arch):
    model = models.resnet50(pretrained=False, num_classes=7, scale=params.scale)

    DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    if params.PSEnet_path is not None:
        if os.path.isfile(params.PSEnet_path):
            print("Loading model and optimizer from checkpoint '{}'".format(params.PSEnet_path))
            checkpoint = torch.load(params.PSEnet_path, map_location=DEVICE)

            # model.load_state_dict(checkpoint['state_dict'])
            d = collections.OrderedDict()
            for key, value in checkpoint['state_dict'].items():
                tmp = key[7:]
                d[tmp] = value
            model.load_state_dict(d)

            print("Loaded checkpoint '{}' (epoch {})"
                  .format(params.PSEnet_path, checkpoint['epoch']))
            sys.stdout.flush()
        else:
            print("No checkpoint found at '{}'".format(params.PSEnet_path))
            sys.stdout.flush()

    model.eval()
    scaled_img = scaleimg(org_img[:,:,[2,1,0]])
    #scaled_img = np.expand_dims(scaled_img,axis=0)
    scaled_img = Image.fromarray(scaled_img)
    scaled_img = scaled_img.convert('RGB')
    scaled_img = transforms.ToTensor()(scaled_img)
    scaled_img = transforms.Normalize(mean=[0.0618, 0.1206, 0.2677], std=[1.0214, 1.0212, 1.0242])(scaled_img)
    scaled_img = torch.unsqueeze(scaled_img,0)
    #img = scaleimg(org_img)
    #img = img[:,:,[2,1,0]]
    #img = np.expand_dims(img,axis=0)
    #img = Image.fromarray(img)
    #img = img.convert('RGB')
    #img = torch.Tensor(img)
    #img = img.permute(0,3,1,2)
    scaled_img = Variable(scaled_img)

    outputs = model(scaled_img)

    score = torch.sigmoid(outputs[:, 0, :, :])
    outputs = (torch.sign(outputs - params.binary_th) + 1) / 2

    text = outputs[:, 0, :, :]
    kernels = outputs[:, 0:params.kernel_num, :, :] * text

    score = score.data.cpu().numpy()[0].astype(np.float32)
    text = text.data.cpu().numpy()[0].astype(np.uint8)
    kernels = kernels.data.cpu().numpy()[0].astype(np.uint8)
    pred = pypse(kernels, params.min_kernel_area / (params.scale * params.scale))

    scale = (org_img.shape[1] * 1.0 / pred.shape[1], org_img.shape[0] * 1.0 / pred.shape[0])
    label = pred
    label_num = np.max(label) + 1
    bboxes = []
    for i in range(1, label_num):
        points = np.array(np.where(label == i)).transpose((1, 0))[:, ::-1]

        if points.shape[0] < params.min_area / (params.scale * params.scale):
            continue

        score_i = np.mean(score[label == i])
        if score_i < params.min_score:
            continue

        rect = cv2.minAreaRect(points)
        bbox = cv2.boxPoints(rect) * scale
        bbox = bbox.astype('int32')
        bboxes.append(bbox.reshape(-1))
    drawBBox(bboxes,org_img)
    return bboxes


def main(args):
    print ('reading image..')
    image = cv2.imread(args.image)
    print ('detecting text')
    bboxes = detect(image)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='image path')
    parser.add_argument('--img', nargs='?', type=str, default='demo/tr_img_09961.jpg',
                        help='Path to test image')
    args = parser.parse_args()
    main(args)











