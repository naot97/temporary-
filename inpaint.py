import numpy as np
import scipy.optimize as optimize
import scipy.sparse as sparse
import scipy.linalg as linalg
from timeit import default_timer
from utils import ROFImg
from detectnoise import *
#from imgaug import augmenters as iaa
from skimage.util import random_noise, img_as_float





class Inpaint(ROFImg):
    def __init__(self):
        ROFImg.__init__(self)

#--------------------------------- New -----------------------------------------------------------------------#
    def denoise_sq_3channel(self,x,b,l):
        x = x.reshape((self.M,self.N,3))
        x1 = x[:,:,0].flatten()
        x2 = x[:,:,1].flatten()
        x3 = x[:,:,2].flatten()

        b1 = b[:,:,0].flatten()
        b2 = b[:,:,1].flatten()
        b3 = b[:,:,2].flatten()

        diff = 0.5*l*linalg.norm(b - x)**2
        tv1 = linalg.norm(self.Dx.dot(x1))**2  + linalg.norm(self.Dy.dot(x1))**2
        tv2 = linalg.norm(self.Dx.dot(x2))**2  + linalg.norm(self.Dy.dot(x2))**2
        tv3 = linalg.norm(self.Dx.dot(x3))**2  + linalg.norm(self.Dy.dot(x3))**2
        tv = tv1 + tv2 + tv3

        return diff + tv

    def denoise_sq_3channel_grad(self, x, b, l):
        x = x.reshape((self.M,self.N,3))
        x1 = x[:,:,0].flatten()
        x2 = x[:,:,1].flatten()
        x3 = x[:,:,2].flatten()

        diff_grad = (2*0.5*l*(x - b)).flatten()
        tv1_grad = 2 * (self.Dx.T.dot(self.Dx.dot(x1)) + self.Dy.T.dot(self.Dy.dot(x1))).reshape(self.M,self.N)
        tv2_grad = 2 * (self.Dx.T.dot(self.Dx.dot(x2)) + self.Dy.T.dot(self.Dy.dot(x2))).reshape(self.M,self.N)
        tv3_grad = 2 * (self.Dx.T.dot(self.Dx.dot(x3)) + self.Dy.T.dot(self.Dy.dot(x3))).reshape(self.M,self.N)
        tv_grad = np.zeros((self.M,self.N,3))
        tv_grad[:,:,0] = tv1_grad
        tv_grad[:,:,1] = tv2_grad
        tv_grad[:,:,2] = tv3_grad
        tv_grad = tv_grad.flatten()

        return diff_grad + tv_grad

    def denoise_3channel(self,noise):
        l = self.l 
        out = np.zeros_like(noise)
        b = noise
 
        optim_output = optimize.minimize(lambda  x : self.denoise_sq_3channel(x,b,l),
                                        np.zeros(self.M*self.N*3),
                                        method = 'L-BFGS-B',
                                        jac = lambda  x : self.denoise_sq_3channel_grad(x,b,l),
                                        options={'disp':True,'ftol' : 1e-30 })

        out_img = optim_output['x'].reshape(self.M,self.N,3)
        return out_img.astype(int)
#-----------------------------------------------------------------------------------------------------------#

    def denoise_smoothed_sq(self, x, b, l=1.1):
        return 0.5*l*linalg.norm(b - x)**2 + (linalg.norm(self.Dx.dot(x))**2 + linalg.norm(self.Dy.dot(x))**2)

    def denoise_smoothed_sq_grad(self, x, b, l=1.1):
        return 2*(0.5*l*(x - b) + (self.Dx.T.dot(self.Dx.dot(x)) + self.Dy.T.dot(self.Dy.dot(x))))
    


    def denoising(self, noise ):
        l = self.l
        image_result = np.zeros_like(noise)

        for i in range(3):
            b = noise[:,:,i].flatten()

            optim_output = optimize.minimize(lambda x: self.denoise_smoothed_sq(x,b,l),
                                    np.zeros(self.M * self.N),
                                    method='L-BFGS-B',
                                    jac=lambda x: self.denoise_smoothed_sq_grad(x,b,l),
                                    options={'disp':False, 'ftol' : 1e-30}
                                    #,callback= lambda xk : self.f.append(self.denoise_smoothed_sq(xk,b,l)[i])
                                    )

            image_smooth = optim_output['x']
            image_result[:,:,i] = image_smooth.reshape((self.N,)*2)
        
        return image_result.astype(int)
    def inpainting_smoothed_sq(self,x, a,b, l=0.5):
        #print(l)
        return (linalg.norm(self.Dx.dot(x))**2 + linalg.norm(self.Dy.dot(x))**2) + 0.5 *l* a.dot(linalg.norm(b - x)**2)

    def inpainting_smoothed_sq_grad(self,x,a, b, l=0.5):
        return 2*(0.5*a*l*(x - b) + (self.Dx.T.dot(self.Dx.dot(x)) + self.Dy.T.dot(self.Dy.dot(x))))
    
    def inpainting_simulate(self):
        ori = self.get_rgb(self.fname)
        ori = ori[:self.M,:self.N,:]


        damaged = self.get_simulate_data(ori,"gauss")
        out1=damaged.copy()
        out3 = damaged.copy()
        median1=damaged.copy()

        rows0,cols0 = algorithm(3,damaged)
        out = self.inpainting(damaged,rows0,cols0)


#------------------------------------------------ Thay doi-----------------------------------------------------------------------#
        out2= self.denoise_3channel(damaged)
        #out2 =self.denoising(damaged)
#--------------------------------------------------------------------------------------------------------------------------------#
        median,t = self.median_filter(damaged,3)

        noisy = damaged.copy()
        noisy = noisy.astype(int)
        noisy[rows0, cols0,:] = 0

        out3[rows0, cols0,:] = out2[rows0, cols0,:]
        out1[rows0, cols0,:] = out[rows0, cols0,:]
        median1[rows0, cols0,:]= median[rows0, cols0,:]

        print('noisy :',self.eval_mse(ori[2:254,2:254,:],damaged[2:254,2:254,:]))
        print('median filter  :',self.eval_mse(ori[2:254,2:254,:],median[2:254,2:254,:]))
        print('median filter + detect noise :', self.eval_mse(ori[2:254,2:254,:], median1[2:254,2:254,:]) )

        print('convex without detection:',self.eval_mse(ori[2:254,2:254,:],out2[2:254,2:254,:]))
        print('convex :',self.eval_mse(ori[2:254,2:254,:],out[2:254,2:254,:]))

        print('convex + detect noisy  :',self.eval_mse(ori,out3))
        print('convex + detect noisy plus :',self.eval_mse(ori[2:254,2:254,:],out1[2:254,2:254,:]))
        self.show_figure(ori,damaged,noisy,out2,out1,out3,median,median1)


    def inpainting(self,noise, rows0, cols0):

        l = self.l
        a = np.ones((self.M,self.N))
        a[rows0, cols0] = 0
        a = a.flatten()
        A=[a,a,a]


        image_result = np.zeros_like(noise)


        for i in range(3):
            b = noise[:,:,i].flatten()

            optim_output = optimize.minimize(lambda x: self.inpainting_smoothed_sq(x,A[i],b,l),
                                    np.zeros(self.M * self.N),
                                    method='L-BFGS-B',
                                    jac=lambda x: self.inpainting_smoothed_sq_grad(x,A[i],b,l),
                                    #options={'disp':False, 'ftol' : 1e-30},callback= lambda xk : self.f.append(self.inpainting_smoothed_sq(xk,a,b,l)[0]))
                                    options={'disp':False, 'ftol' : 1e-35}
                                    #,callback= lambda xk : self.f.append(self.inpainting_smoothed_sq(xk,A[i],b,l)[i])
                                    )


            image_smooth = optim_output['x']
            image_result[:,:,i] = image_smooth.reshape((self.N,)*2)
        
        return image_result.astype(int)
        
####
def rateNoisy(ori,damaged,thres=0):
    h, w = ori.shape[:2]
    sum0=sum1=sum2=0
    for i in range(h):
        for j in range(w):
            if(abs(ori[i,j,0]-damaged[i,j,0])>thres):
                sum0+=1
            if(abs(ori[i,j,1]-damaged[i,j,1])>thres):
                sum1+=1
            if(abs(ori[i,j,2]-damaged[i,j,2])>thres):
                sum2+=1
    n=h*w
    return sum0/n, sum1/n,sum2/n

####

test = Inpaint()
test.fname = "./images/lana.jpg"
lambdas = [7]
f = list()
tt=0
for l in lambdas:
    tt+=1
    test.l = l
    test.inpainting_simulate()
    f.append(test.f)
    test.f = list()

