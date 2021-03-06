import torch
import torch.nn as nn
import torch.optim as optim
import os

from torch.optim import lr_scheduler
from torchvision import models
from torchsummary import summary
# from adabelief_pytorch import AdaBelief
from models.cosine_annearing_with_warmup import CosineAnnealingWarmUpRestarts
# from warmup_scheduler import GradualWarmupScheduler
from models.utils import *
# cosine_annearing_with_warmup is referenced by below github repository.
# https://github.com/katsura-jp/pytorch-cosine-annealing-with-warmup

def get_model(device, iters,freeze_conv=False, scheduler='cos', step_size=7,
              use_tpu=False, lr=0.001, momentum=0.9, weight_decay=5e-4,
              old_optimizer=False, opt='SGD', nestrov=True):
    '''Create and return the model based on ResNet-50.
    
    Args:
        device (obj): the device where the model will be trained (e.g. cpu or gpu)
        fine_tuning (bool): whether fine-tuning or not
        
    Returns:
        model_ft (obj): the model which will be trained
        criterion (obj): the loss function (e.g. cross entropy)
        optimizer_ft (obj): the optimizer (e.g. Adam)
        exp_lr_scheduler (obj): the learning scheduler (e.g. Step decay)
    '''
    # Get the pre-trained model
    model_ft = models.resnet50(pretrained=True)
    if freeze_conv:
        for param in model_ft.parameters():
            param.requires_grad = False
            
    # Change fully connected layer
    num_ftrs = model_ft.fc.in_features
    model_ft.fc = nn.Linear(num_ftrs, 3)
    model_ft = model_ft.to(device)
    
    # Set loss function, optimizer and learning scheduler
    criterion = nn.CrossEntropyLoss()
    if use_tpu:
        import torch_xla.core.xla_model as xm
        lr = 0.001 * xm.xrt_world_size()
    
    if opt == 'SGD':
        if old_optimizer:
            optimizer_ft = optim.SGD(model_ft.parameters(), lr=lr, momentum=momentum)
        else:
            optimizer_ft = get_SGD(model_ft, 'SGD', lr, momentum, weight_decay, nestrov)
    elif opt == 'Adam':
        optimizer_ft = optim.Adam(model_ft.parameters(), lr=lr)
    else: # Adabelief
        assert False, 'You should select an optimizer.'
        # optimizer_ft = AdaBelief(model_ft.parameters(), lr=lr, eps=1e-8, betas=(0.9,0.999),
        #                          weight_decay=0, amsgrad=False, weight_decouple=False,
        #                          fixed_decay=False, rectify=False)
    
    if scheduler == 'step':
        exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=step_size, gamma=0.1)
        # exp_lr_scheduler = GradualWarmupScheduler(optimizer_ft, multiplier=1, total_epoch=5, after_scheduler=exp_lr_scheduler)
    elif scheduler == 'cos': 
        # cosine annealing
        if old_optimizer:
            exp_lr_scheduler = CosineAnnealingWarmUpRestarts(optimizer_ft,
                                                            T_0=5, T_mult=1,
                                                            eta_max=0.1, T_up=10)
        else:
            exp_lr_scheduler = get_cosine_schedule_with_warmup(optimizer_ft,
                                                        iters,
                                                        num_warmup_steps=iters*0)
    else: # no decay
        exp_lr_scheduler = None
    
    return model_ft, criterion, optimizer_ft, exp_lr_scheduler

def save_model(trained_model, cfg):
    if not os.path.isdir(cfg['out_dir']):
        os.makedirs(cfg['out_dir'])

    torch.save(model, f'{cfg["out_dir"]}/{cfg["purpose"]}/{cfg["purpose"]}_model_{i}.pt')

def load_model(cfg):
    model_dir = f'trained_models/{cfg["purpose"]}'
    trained_models = []
    for i in range(cfg['fold']):
        trained_models.append(torch.load(f'{model_dir}/{cfg["purpose"]}_model_{i}.pt'))

    summary(trained_models[0], (3, 224, 224))
    return trained_models