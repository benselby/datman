function SPINS_DTIQAv3(site,QAdate,ynNyq)

%%
%%  This code is written for a specific multi-site study with 3 expected sites: site= 'CMH, 'MRC', 'ZHH'.
%%  All scanners are 3T, both 'CMH and 'ZHH' are GE scanners while 'MRC' is a Siemens (which produces DCM mosaic) so loading
%%  of DTI data is site-specific. 

%%  'QAdate' is the name of a folder that contains the data to be processed.

%%  'ynNyq' is a variable that determines whether or not ('y' or 'n') the Nyquist ghost will be measured: the Nyquist ghost will
%%   only be measure for no ASSET factor data (i.e., no parallel imaging). 
%%  
%%   
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%     SETTING UP PART : checks for the case (which site) we are processing
%%
%%  This part sets up the paths to the data, loads the data, creates the output textfiles.
%%  To use it:         
%%  set MAINDIR to your path. A folder called ProcessedResults is created in MAINDIR/QAdate/
%%  with all output images and some textfiles. Cumulative textfiles are created directly in
%%  MAINDIR and named with the 'site'.
%%
%%  You can skip to MAIN PART if you already have the DTI data loaded as a 3D matrix and 
%%  you will use your own input/output formats
%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

MAINDIR=strcat('/home/sofia/data/SPINS-QA/')

MAINDIR2=strcat(MAINDIR,QAdate,'/')


%default values
ndir=60;
nsl=10;
nb0=5; 

switch site
    case 'MRC'
        nb0=6;
    otherwise
        nsl=7;
end


dirpath='ProcessedResults/';
if~isdir(strcat(MAINDIR2,dirpath))
    mkdir(MAINDIR2,dirpath)
end
%% site specific formatting
        dir2=dir(MAINDIR2);
        names2={dir2.name};
        lnames2=length(names2) % cause 2 are . and ..Ex1267Se02Im00001
        n=0;
        for i=1:lnames2
            fname=names2{i};
            if ~isempty(strfind(fname,'Ex'))
                n=n+1;
            end
        end

        lnames2=n

switch site
    case 'MRC'

        if lnames2~=(ndir+nb0)
            'wrong number of files!'
            pause
        end
                
end


imgfname=names2{3}
Exnumchk=strfind(imgfname,'Ex')            
Senumchk=strfind(imgfname,'Se')    
Exnum=str2num(imgfname(Exnumchk+2:Senumchk-1))            
Senum=str2num(imgfname(Senumchk+2:Senumchk+3))
        
switch site
    case 'MRC'
       
        N=128;
        Dsort=loadMPRC(MAINDIR2,nsl,N);
        
    otherwise
        Exstr=num2str(Exnum,'%05d')
        Sestr=num2str(Senum,'%02d')
        filnamecheck=strcat(MAINDIR2,'Ex',Exstr,'Se',Sestr,'Im00001.dcm')
        infoDTIcheck=dicominfo(filnamecheck)
%         sedescr=infoDTIcheck.SeriesDescription
   
   
        
end
%%
'closing all images..'
pause(1)
close all 

%%
disp(' ')
disp('OUTPUT TO : <QAdirectory>/<date>/DTI/')
disp(' ')
disp(['OUTPUT txt files:     '])
disp(['(in <date>/Processed) ','Nyq_ratiob0each'])
disp(['                      ','PixelShift'])
disp(['                      ','SNR_datab0each'])
disp(['                      ','SNR_dataDWIeach'])
disp(['(in MAINDIR)          ','Nyq_ratiob0total'])
disp(['                      ','PixelShiftAveGradDir'])
disp(['                      ','SNR_allb'])
disp(' ')
disp(['OUTPUT jpg images:','b0_NoiseHistSuperimposed'])
disp(['                 ','ColPixsh'])
disp(['                 ','DiffMasks'])
disp(['                 ','DWI_NoiseHistSuperimposed'])
disp(['                 ','ImgNyqRatROIsMask_b0num#'])
disp(['                 ','Masks'])
disp(['                 ','PlotsAvePixsh'])
disp(['                 ','PLotsSNR_ALLdataAVESTD'])
disp(['                 ','PLotsSNR_eachDWI'])
disp(['                 ','PLotsSNRNyq_eachb0'])
disp(['                 ','RadPixsh'])
disp(['                 ','Sampleb0_DiffRoiNoiseHist'])
disp(['                 ','SampleDWI_DiffRoiNoiseHist'])
disp(' ')

%% Make TXT filenames and open files if needed

outflname1=strcat(MAINDIR2,dirpath,'SNR_datab0each.txt')   
fid1=fopen(outflname1,'w')
count=fprintf(fid1,'%s \t %s \t \t  %s \t  %s \t   %s \t   %s\n', 'b=0#', 'stdNoise', 'aveNoise','aveSignal', 'stdSignal','SNR(=aveS/stdN)');  

if ynNyq=='y'
    outflname2=strcat(MAINDIR,'TextResults_',site,'/SNR_allb_noASSET.txt') ;  
else
   outflname2=strcat(MAINDIR,'TextResults_',site,'/SNR_allb_wASSET.txt') ;   
end
if exist(outflname2)
    fid2=fopen(outflname2,'at');
else
    fid2=fopen(outflname2,'at');
    count=fprintf(fid2,'%s \t \t \t \t \t \t \t \t %s \t %s \t  %s \t  %s \t %s \t %s  \n', 'QADate','stdSNR_b0', 'aveSNR_b0', 'CoV_SNR_b0(%)','stdSNR_dwi', 'aveSNR_dwi', 'CoV_SNR_dwi(%)');
end

outflname3=strcat(MAINDIR2,dirpath,'SNR_dataDWIeach.txt')  
fid3=fopen(outflname3,'w')
count=fprintf(fid3,'%s \t %s \t \t   %s \t  %s \t   %s \t   %s\n', 'GradDir#', 'stdNoise', 'aveNoise', 'aveSignal','stdSignal','SNR(=aveS/stdN)');  


outflname4=strcat(MAINDIR2,dirpath,'Nyq_ratiob0each.txt')   
fid4=fopen(outflname4,'w')
count=fprintf(fid4,'%s   \t %s  \t %s  \t %s \n', 'b#', 'aveNyq', 'avenoise','Nyqratio');  

if ynNyq=='y'
    outflname5=strcat(MAINDIR,'TextResults_',site,'/Nyq_ratiob0total_noASSET.txt') 


    if exist(outflname5)
        fid5=fopen(outflname5,'at')
    else
        fid5=fopen(outflname5,'at')
        count=fprintf(fid5,'%s  \t \t \t \t \t \t \t \t%s  \t  %s  \t %s\n', 'QADate', 'STDNyqratio','AVENyqratio','CoV_Nyqratio');  
    end
end
flname=strcat(MAINDIR2,dirpath,'PixelShift.txt'); 
fidps=fopen(flname,'w');
count=fprintf(fidps,'%s \t %s\t%s\t%s   \n', 'GradDir#','Ave.radial pixsh', 'Max.radial pixsh', 'Ave.col pixsh');  

if ynNyq=='y'
    flname2=strcat(MAINDIR,'TextResults_',site,'/PixelShiftAveGradDir_noASSET.txt') ;
else
    flname2=strcat(MAINDIR,'TextResults_',site,'/PixelShiftAveGradDir_wASSET.txt') ;
end

if exist(flname2)
    fidps2=fopen(flname2,'at');
else
    fidps2=fopen(flname2,'at');
    count=fprintf(fidps2,'%s \t \t  \t \t \t \t \t \t %s \t %s \t %s   \n', 'QADate','AVE Ave.radpixsh', 'AVE Max.radpixsh', 'AVE Ave.colpixsh');  
end

if ynNyq=='y'
    flnameADCFA=strcat(MAINDIR,'TextResults_',site,'/ADC_FA_noASSET.txt') ;
else
    flnameADCFA=strcat(MAINDIR,'TextResults_',site,'/ADC_FA_wASSET.txt') ;
end

if exist(flnameADCFA)
    fidadc=fopen(flnameADCFA,'at');
else
    fidadc=fopen(flnameADCFA,'at');
    count=fprintf(fidadc,'%s \t \t  \t \t \t \t \t \t %s \t %s \t %s   \t %s   \t %s \n', 'QADate','AVE ADC', 'STD ADC','CV ADC(%)', 'AVE FA','STD FA');  
end

%% average 3 central slices (cause of low SNR)- may want to change this dep on slice thickness

ctrsl=floor(nsl/2)
numslave=3; % odd number
numslside=floor(numslave/2);
disp(strcat('Processing Slices #',num2str(ctrsl-numslside),' to #',num2str(ctrsl+numslside),' averaged'))
close all
 
DWI4d=[];

switch site
    case 'MRC'
        
        % getting DWI4d for Seimens
        DWI4d=Dsort(:,:,:,ctrsl-numslside:ctrsl+numslside);

    case 'CMH'
       % getting DWI4d for CMH
        for sl=ctrsl-numslside:ctrsl+numslside
            sl
            DWIx=load_singleDWI_SPINS(MAINDIR2,nsl,ndir,sl);
            DWI4d=cat(4,DWI4d,DWIx);
        end 
    
    case 'ZHH'
        % getting DWI4d for ZHH
        for sl=ctrsl-numslside:ctrsl+numslside
            sl
            DWIx=load_singleDWI_NY(MAINDIR2,nsl,ndir,sl);
            DWI4d=cat(4,DWI4d,DWIx);
        end 
    
        
end
    
DWI=mean(DWI4d,4);

figure(111)
% set(111,'OuterPosition',[1 1 scrsz(3)/2 scrsz(4)])
for i=1:ndir+nb0
        subplot(8,9,i)
        imagesc(DWI(:,:,i))
        set(gca,'fontsize',6)
        title(['Image #',num2str(i)])
        axis image
        axis off
end

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%     MAIN PART : asssumes you have a 3D matrix called DWI 
%%                 with dim1&2=AXIAL images, dim3=all volumes (T2w (ie, b=0) + DWIs)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

[Nx,Ny,numimgs]=size(DWI)


%%%%%%%%%%%%%%%%%%  PART A %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
   
%% Getting masks and Pixel shifts
% 
    disp('Measuring Pixel Shifts')


    [averadpsh,maxradpsh,avecolpsh,SigM]=AdjDiffMasksallv2clean(DWI,ndir); % this is NOT site-specific for SPINS (uses imagefill method instead of thresholding)
    
    aveaverad=mean(averadpsh);
    avemaxrad=mean(maxradpsh);
    aveavecol=mean(avecolpsh);
    
    for i=1:numimgs-nb0
        j=nb0+i;
        count=fprintf(fidps,'%s  \t  \t\t%6.2f \t \t \t \t %d     \t \t \t %6.2f   \n',num2str(i,'%02d'),averadpsh(j), maxradpsh(j),avecolpsh(j))  ;
    end

    count=fprintf(fidps2,'%s    \t\t%6.2f \t\t\t%6.2f     \t\t%6.2f   \n',QAdate,aveaverad,avemaxrad,aveavecol);

    'done pixel shifts'
    
    
 %%%%%%%%%%%%%%%%%%  PART B %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
   
      
%% NEW METHOD: getting measure of noise from central ROI in difference image (using phantom radius=35/128 pixels)
       disp('Measuring Noise from Difference Images of b=0')
 
          phantrad=35*(Nx/128);
       
       Diff(1:Nx,1:Ny,1:nb0)=0;
       Diff(1:Nx,1:Ny,1)=double(DWI(1:Nx,1:Ny,2)-DWI(1:Nx,1:Ny,1));
       nd2TOT=[];
      for b=2:nb0
       
            Diff(1:Nx,1:Ny,b)=double(DWI(1:Nx,1:Ny,b)-DWI(1:Nx,1:Ny,1));
            N2=floor(Nx/2)
         
            noisemskctr=makecirc(Nx,N2,N2,phantrad);
            Diff2d(1:Nx,1:Ny)=Diff(1:Nx,1:Ny,b);
            nd2{b-1}=Diff2d(find(noisemskctr));
             std2ALL(b)=std(nd2{b-1});
                ave2ALL(b)=mean(nd2{b-1});
               % check that noise is not Rician
                noiseratio=ave2ALL(b)/std2ALL(b);
                [nd2hist,xhist2]=hist(nd2{b-1},20);
                
            if b==2
                figure(100)
                subplot(2,2,1)
                    imagesc(Diff(1:Nx,1:Ny,b))
                    axis image
                    axis off
                    title(['T2w image b=0 Img#',num2str(b)])
                subplot(2,2,2)
                    XX=Diff(1:Nx,1:Ny,b);
                    XX(find(noisemskctr))=max(max(Diff(1:Nx,1:Ny,b)))*.8;
                    imagesc(XX)
                    axis image
                    axis off
                subplot(2,2,3)
                    plot(nd2{b-1})
                    title(['ave(noise)=',num2str(ave2ALL(b),'%5.2f'),' std(noise)=',num2str(std2ALL(b),'%5.2f'),' noiseratio=',num2str(noiseratio,'%5.2f')])
                subplot(2,2,4)
                    plot(xhist2,nd2hist)
                    title('noise histogram')
            end
            
            nd2TOT=cat(2,nd2TOT, nd2{b-1});
      end 
    
      % use same noise (from img#1-img#2) for std(noise) calc for images #1 & #2
      std2ALL(1)=std2ALL(2);
      ave2ALL(1)=ave2ALL(2);
      
      [nd2hist,xhist2]=hist(nd2TOT,20); 
      clear ave2 std2 nd2
      nd2=nd2TOT(:);
      ave2b0=mean(nd2)
      std2b0=std(nd2)
      noiseratio=ave2b0/std2b0;
      
      figure(150)
      subplot(1,2,1)
      plot(nd2TOT)
      title(['ave(noise)=',num2str(ave2b0,'%5.2f'),' std(noise)=',num2str(std2b0,'%5.2f'),' noiseratio=',num2str(noiseratio,'%5.2f')])
       subplot(1,2,2)     
      plot(xhist2,nd2hist)
      title('TOTAL noise histogram')
      
     
   
%             
%% NEW METHOD: getting measure of noise from central ROI in difference image
       disp('Measuring Noise from Difference of DWIs')
       clear Diff nd2*
       
       ngrad=numimgs-nb0
       Diff(1:Nx,1:Ny,1:ngrad)=0;
       Diff(1:Nx,1:Ny,1)=double(DWI(1:Nx,1:Ny,2+nb0)-DWI(1:Nx,1:Ny,1+nb0));
       nd2TOT=[];
       
       figure(200)
      for b=2:ngrad
       
            Diff(1:Nx,1:Ny,b)=double(DWI(1:Nx,1:Ny,b+nb0)-DWI(1:Nx,1:Ny,1+nb0)); %difference always wrt first DWI
            
            N2=floor(Nx/2);
            noisemskctr=makecirc(Nx,N2,N2,phantrad);
            Diff2d(1:Nx,1:Ny)=Diff(1:Nx,1:Ny,b);
            nd2{b-1}=Diff2d(find(noisemskctr));
            std2ALL(nb0+b)=std(nd2{b-1});
            ave2ALL(nb0+b)=mean(nd2{b-1});
            
             % check that noise is not Rician
            noiseratio=ave2ALL(nb0+b)/std2ALL(nb0+b);
            [nd2hist,xhist2]=hist(nd2{b-1},20);
            
             
            if b==2
            subplot(2,2,1)
                imagesc(Diff(1:Nx,1:Ny,b))
                axis image
                axis off
                title(['DiffImg grad dir b>0 Img#',num2str(b)])
            subplot(2,2,2)
                XX=Diff(1:Nx,1:Ny,b);
                XX(find(noisemskctr==0))=0;
%             XX(find(noisemskctr))=max(max(Diff(1:Nx,1:Ny,1)))*.8;
                imagesc(XX)
                axis image
                axis off
            subplot(2,2,3)
                plot(nd2{b-1})
                title(['ave(noise)=',num2str(ave2ALL(nb0+b),'%5.2f'),' std(noise)=',num2str(std2ALL(nb0+b),'%5.2f'),' noiseratio=',num2str(noiseratio,'%5.2f')])
            subplot(2,2,4)
                plot(xhist2,nd2hist)
                title('noise histogram')
            
            end
            
             nd2TOT=cat(2,nd2TOT, nd2{b-1});
            
      end 
     
      % use same noise (from dwi#1-dwi#2) for std(noise) calc for images
      std2ALL(nb0+1)=std2ALL(nb0+2);
      ave2ALL(nb0+1)=ave2ALL(nb0+2);
      
      [nd2hist,xhist2]=hist(nd2TOT,20); 
      clear ave2 std2 nd2
      nd2=nd2TOT(:);
      ave2=mean(nd2)
      std2=std(nd2)
      noiseratio=ave2/std2;
      
      figure(300)
      subplot(1,2,1)
      plot(nd2TOT)
      title(['b>0 ave(noise)=',num2str(ave2,'%5.2f'),' std(noise)=',num2str(std2,'%5.2f'),' noiseratio=',num2str(noiseratio,'%5.2f')])
       subplot(1,2,2)     
      plot(xhist2,nd2hist)
      title('TOTAL noise histogram')
      
     
            
%% Getting SNR measurements
            
  disp('Measuring SNR for all b=0 and b>0')
  
  Stot=[];
    for b=1:numimgs
        
         I(1:Nx,1:Ny)=DWI(:,:,b);
          
        
        
         Smat=I(find(noisemskctr));
         S=Smat(:)';
         aveS(b)=mean(S);
         stdS(b)=std(S);
         
        
              
         SNR(b)= aveS(b)/std2ALL(b);
         
         II=I*0;
         II(find(noisemskctr))=I(find(noisemskctr));
         Stot=cat(1,Stot,II(:)');
       
    end
    
    
    SNRb0TOT=mean(SNR(1:nb0))
    STD_SNRb0TOT=std(SNR(1:nb0))
    SNRTOT=mean(SNR(nb0+1:numimgs))
    STD_SNRTOT=std(SNR(nb0+1:numimgs))
    
    figure(400)
    plot(SNR,'bo-')
    hold on
    plot([nb0+1:numimgs],SNR(nb0+1:numimgs),'b*-')
    title(['SNR b=0 images:',num2str(SNRb0TOT,'%05.2f'),'(',num2str(STD_SNRb0TOT),')  ||    SNR DWIs:',num2str(SNRTOT,'%05.2f'),'(',num2str(STD_SNRTOT),')'])
    
    AVESNRb0=mean(SNR(1:nb0))
    STDSNRb0=std(SNR(1:nb0))
    CV_SNRb0=STDSNRb0*100/AVESNRb0
    AVESNRdwi=mean(SNR(1+nb0:numimgs))
    STDSNRdwi=std(SNR(1+nb0:numimgs))
    CV_SNRdwi=STDSNRdwi*100/AVESNRdwi
         
     
       for b=1:nb0
                count=fprintf(fid1,'%d \t \t  %6.2f  \t \t \t %6.2f \t \t %6.2f  \t \t %6.2f  \t \t %6.2f  \n', b, std2ALL(b), ave2ALL(b),aveS(b), stdS(b),SNR(b)) ;
           
       end
       for b=nb0+1:numimgs 
                count=fprintf(fid3,'%d  \t \t \t %6.2f  \t \t \t \t %6.2f \t   %6.2f \t  \t %6.2f  \t \t %6.2f  \n', b-nb0, std2ALL(b), ave2ALL(b), aveS(b),stdS(b),SNR(b)) ;
               
       end
       
       count=fprintf(fid2,'%s \t \t %6.4f \t  %6.4f \t \t %6.4f \t \t  %6.4f  \t \t  %6.4f \t \t %6.4f\n', QAdate, STDSNRb0, AVESNRb0, CV_SNRb0,STDSNRdwi, AVESNRdwi, CV_SNRdwi);
        

 %   Plotting results for SNR for DWIs

    figure(500)
    subplot(3,1,1)
    plot([1:numimgs-nb0],aveS(nb0+1:numimgs),'b*-')
    xlabel('Gradient Direction')
    axis([1 numimgs-nb0 0 max(aveS(nb0+1:numimgs))*1.2])
    title('Ave. Signal')
    subplot(3,1,2)
    plot([1:numimgs-nb0], std2ALL(nb0+1:numimgs),'b*-')
    xlabel('Gradient Direction')
    axis([1 numimgs-nb0 0 max(std2ALL(nb0+1:numimgs))*1.2])
    title('Std noise')
    subplot(3,1,3)
    plot([1:numimgs-nb0],SNR(nb0+1:numimgs),'b*-')
    xlabel('Gradient Direction')
    axis([1 numimgs-nb0 0 max(SNR(nb0+1:numimgs))*1.2])
    title('SNR')

%%%%%%%%%%%%% PART C %%%%%%%%%%%%%%%%%%%%%%%
    
%% Getting Nyquist Ghost info
       

if ynNyq=='y'
  disp('Measuring Nyquist Ghost')
    for b=1:nb0
        I_B0(1:Nx,1:Ny)=DWI(:,:,b); 
        Smask=SigM(:,:,1);
        [ndNyq,XX2]=noisedistNyqSmask(I_B0,Smask);
        aveNyq(b)=mean(ndNyq);

        [ndnoise,XX3]=noisedist_DTISmask(I_B0,Smask);
        avenoise(b)=mean(ndnoise);
        
        
        XX=(XX2+XX3)/2;
        maxv=max(max(XX));
         
         figure(20+b)
        subplot(2,1,1)
        imagesc(XX,[0 maxv/2])
        colormap(jet)        
        axis image
        axis off
        title(['b=0 Img#', num2str(b),' ROI regions for Nyquist ratio'])
        subplot(2,1,2)
        imagesc(Smask)        
        axis image
        axis off
        title(['Signal mask (excluded pixels)'])
   
        ratNyq(b)=aveNyq(b)./avenoise(b);

    
        count=fprintf(fid4,'%d \t   \t %6.4f \t %6.4f  \t %6.4f  \n', b,aveNyq(b),avenoise(b), ratNyq(b));  
    end
    
    STDNyqrat=std(ratNyq)
    AVENyqrat=mean(ratNyq)
    CV_Nyqrat=STDNyqrat*100/AVENyqrat
    
    count=fprintf(fid5,'%s \t \t %6.4f   \t \t %6.4f \t  \t %6.4f   \n',QAdate, STDNyqrat,AVENyqrat,CV_Nyqrat); 
    
    'done Nyq'
  
%   Plotting results for SNR and Nyquist Ratio (b=0) 
   figure(450)
    subplot(4,1,1)
    plot([1:nb0],aveS(1:nb0),'b*-')
    xlabel('b=0 Image# ')
    axis([1 nb0 0 max(aveS(1:nb0))*1.2])
    title('Ave. Signal')
    subplot(4,1,2)
    plot([1:nb0], std2ALL(1:nb0),'b*-')
    xlabel('b=0 Image# ')
    axis([1 nb0 0 max(std2ALL(1:nb0))*1.2])
    title('Std noise')
    subplot(4,1,3)
    plot([1:nb0],SNR(1:nb0),'b*-')
    xlabel('b=0 Image#')
    axis([1 nb0 0 max(SNR(1:nb0))*1.2])
    title('SNR')
    subplot(4,1,4)
    plot([1:nb0],ratNyq(1:nb0),'b*-')
    xlabel('b=0 Image#')
    axis([1 nb0 0 max(ratNyq(1:nb0))*1.2])
    title(['Ratio of Nyquist ghost: AVE(STD) =',num2str(AVENyqrat,'%03.3f'),'(',num2str(STDNyqrat,'%03.3f'),')'])
end

%%%%%%%%%%%%%%  PART D %%%%%%%%%%%%%%%%%
%% Calc FA and ADC     


addpath ~/MATLAB/prgms/DTI/DTI_code_Ryan/

%% prgm assumes a single b=0 + N dwi w/ b=1000;
b(1)=0;
b(2:numimgs-(nb0-1))=1000;

Stottmp=Stot(1:nb0,:);
Stotb0=mean(Stottmp,1); %% ave over nb0 b=0 non-DWI
size(Stotb0)

Stot2(1,:)=Stotb0(:);
Stot2(2:ngrad+1,:)=Stot(nb0+1:numimgs,:);

% assume 60 graddir THESE ARE GE DIRECTIONS! CHECK IF MATCH THE ACQUISITION
q=[1.000000 0.000000 0.000000;
    0.361000 0.933000 0.000000;
    -0.255000 0.565000 0.785000;
    0.861000 -0.464000 0.210000;
    -0.307000 -0.766000 0.564000;
    -0.736000 0.013000 0.677000;
    0.532000 0.343000 0.774000;
    0.177000 0.965000 0.195000;
    0.771000 0.163000 0.615000;
    0.079000 -0.996000 -0.036000;
    0.109000 -0.920000 -0.376000;
    0.302000 -0.779000 -0.549000;
    -0.464000 -0.460000 0.757000;
    -0.464000 0.839000 0.284000;
    -0.529000 0.014000 -0.849000;
    -0.825000 -0.540000 -0.167000;
    0.697000 -0.287000 -0.657000;
    0.479000 -0.338000 -0.810000;
    -0.213000 -0.851000 -0.480000;
    -0.648000 0.736000 -0.195000;
    0.580000 0.745000 0.330000;
    -0.729000 0.197000 -0.656000;
    0.963000 -0.264000 0.054000;
    0.229000 0.507000 0.831000;
    -0.016000 0.171000 -0.985000;
    0.359000 -0.932000 0.051000;
    0.806000 -0.422000 -0.415000;
    -0.045000 0.087000 0.995000;
    -0.177000 0.841000 -0.511000;
    0.946000 0.315000 -0.068000;
    -0.318000 0.257000 -0.912000;
    -0.312000 0.165000 0.936000;
    -0.284000 -0.200000 -0.938000;
    -0.421000 -0.093000 0.902000;
    -0.963000 -0.020000 0.271000;
    -0.881000 0.161000 0.444000;
    0.758000 -0.450000 0.471000;
    -0.684000 0.720000 0.121000;
    0.932000 0.229000 0.281000;
    -0.648000 -0.252000 0.719000;
    0.773000 0.610000 -0.174000;
    0.276000 -0.533000 0.800000;
    -0.555000 0.591000 0.586000;
    0.007000 0.715000 0.699000;
    0.919000 -0.070000 0.388000;
    -0.223000 -0.589000 0.777000;
    -0.544000 -0.730000 0.414000;
    0.867000 -0.477000 -0.145000;
    0.534000 -0.554000 0.639000;
    -0.001000 0.726000 -0.688000;
    -0.611000 -0.791000 -0.027000;
    0.691000 0.503000 -0.519000;
    0.731000 0.475000 0.489000;
    0.024000 -0.380000 -0.925000;
    0.453000 0.646000 0.615000;
    0.432000 -0.820000 0.376000;
    -0.870000 -0.289000 0.399000;
    0.283000 0.912000 -0.298000;
    0.088000 0.393000 -0.915000;
    -0.016000 -0.964000 0.265000];

%%%%%%%%%%%%% need to add in your own tensor computation %%%%%%%%%%%%%%%%%%%%%%%
%[D,e]=calc_dt(Stot2,b',q); % use any preferred method to compute the 3x3 tensor=D
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

Dxx=zeros(Nx,Ny);
Dyy=zeros(Nx,Ny);
Dzz=zeros(Nx,Ny);
tmp=zeros(Nx,Ny);


tmp(:)=D(1,1,:);
Dxx=tmp;
Dxx(Dxx<0)=0;

tmp(:)=D(2,2,:);
Dyy=tmp;
Dyy(Dyy<0)=0;

tmp(:)=D(3,3,:);
Dzz=tmp;
Dzz(Dzz<0)=0;

figure(11)
subplot(1,3,1)
imagesc(Dxx)
title('Dxx')
set(gca,'DataAspectRatio',[1 1 1])
subplot(1,3,2)
imagesc(Dyy)
title('Dyy')
set(gca,'DataAspectRatio',[1 1 1])
subplot(1,3,3)
imagesc(Dzz)
title('Dzz')
set(gca,'DataAspectRatio',[1 1 1])

ADC=(Dxx+Dyy+Dzz)/3;
%% ADC map has lots of NaN instead of zeros so fix that
tmp=zeros(Nx,Ny);
tmp(find(ADC>0))=ADC(find(ADC>0));
clear ADC
ADC=tmp;
%%

ADCv=ADC(find(ADC));
aveADC=mean(ADCv)
stdADC=std(ADCv)
CVADC=stdADC*100/aveADC;
ADCnorm=ADC*0; % initialise it
ADCnorm=(ADC-aveADC)*100/aveADC;
ADCnorm(find(ADC==0))=0;

figure(12)
imagesc(ADCnorm)
colorbar
title(['normalised ADC (wrt ave): ave(std)=',num2str(aveADC,'%03.2e'),'(',num2str(stdADC,'%03.2e'),') mm^{2}/s CV=',num2str(CVADC,'%03.2f'),'%'])
set(gca,'DataAspectRatio',[1 1 1])


'begin FA calc'   


adcv=squeeze(D(1,1,:)+D(2,2,:)+D(3,3,:));
adcv=adcv/3;
whos adcv
tmptensor(1:3,1:3)=0;
Etot(1:size(D,3),1:3)=0;

ind=find(adcv>0.00035);
len=length(ind);

Eig1(1:Nx,1:Ny)=0;
Eig2(1:Nx,1:Ny)=0;
Eig3(1:Nx,1:Ny)=0;

for i=1:len
    ind(i)
    tmptensor(:,:)=D(:,:,ind(i))*1000;
    v1=find(tmptensor>0) ;
    v2=find(tmptensor<0);
    if (isempty(v1)&&isempty(v2)) 
        lambda=[ 0; 0; 0];
    elseif isempty(v2)
        if tmptensor(v1)==Inf
            lambda=[ 0; 0; 0];
        else
            'computing lambda...'
            lambda=eig(tmptensor);
        end
    else
        lambda=eig(tmptensor);
    end
    lambda(find(lambda<0))=0;
    slambda=sort(lambda,'descend');
    Eig1(ind(i))=slambda(1);
     Eig2(ind(i))=slambda(2);
     Eig3(ind(i))=slambda(3);
end


maxc=max(max(Eig1));
figure(13)
subplot(1,3,1)
imagesc(Eig1,[0 maxc])
title('Eig1')
set(gca,'DataAspectRatio',[1 1 1])
subplot(1,3,2)
imagesc(Eig2,[0 maxc])
title('Eig2')
set(gca,'DataAspectRatio',[1 1 1])
subplot(1,3,3)
imagesc(Eig3,[0 maxc])
title('Eig3')
set(gca,'DataAspectRatio',[1 1 1])


FA=Eig1*0;
num=FA;
denom=FA;

dif12=Eig1-Eig2;
dif23=Eig2-Eig3;
dif31=Eig3-Eig1;

Eig1sq=Eig1.*Eig1;
Eig2sq=Eig2.*Eig2;
Eig3sq=Eig3.*Eig3;

num=(dif12.*dif12)+(dif23.*dif23)+(dif31.*dif31);
num=sqrt(num);
denom=Eig1sq+Eig2sq+Eig3sq;
denom=sqrt(denom);

FA(denom>0)=(1/sqrt(2))*(num(denom>0)./denom(denom>0));


figure(14)
subplot(2,2,1)
imagesc(FA, [0 0.1])
title('FA map')
colorbar
set(gca,'DataAspectRatio',[1 1 1])
subplot(2,2,2)
fav=FA(find(FA));
plot(fav)
title('FA values')
subplot(2,2,3)
[n,x]=hist(fav,30);
plot(x,n,'k-')
aveFA=mean(fav);
stdFA=std(fav);
title(['FA mean(std)=',num2str(aveFA,'%5.3f'),'(',num2str(stdFA,'%5.3f'),')'])


%% print to file

count=fprintf(fidadc,'%s \t \t  \t  %03.2e \t %03.2e \t %03.2f \t \t %5.3f   \t %5.3f   \n', QAdate,aveADC, stdADC, CVADC,aveFA,stdFA);  

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%          Print commands   
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


    'Printing Image Files'
    
    % print eddy current distortion measurements
    fig1name=strcat(MAINDIR2,dirpath,'Masks.jpg');
    fig111name=strcat(MAINDIR2,dirpath,'AveCtrlSlices.jpg');
    fig2name=strcat(MAINDIR2,dirpath,'DiffMasks.jpg');
    fig3name=strcat(MAINDIR2,dirpath,'RadPixsh.jpg');
    fig4name=strcat(MAINDIR2,dirpath,'ColPixsh.jpg');
    fig5name=strcat(MAINDIR2,dirpath,'PlotsAvePixsh.jpg');
    print('-f1','-djpeg',fig1name)
    print('-f111','-djpeg',fig111name)
    print('-f2','-djpeg',fig2name)
    print('-f3','-djpeg',fig3name)
    print('-f4','-djpeg',fig4name)
    print('-f5','-djpeg',fig5name)
    
 
    % print SNR stuff
    fig100name=strcat(MAINDIR2,dirpath,'Sampleb0_DiffRoiNoiseHist.jpg');
    fig150name=strcat(MAINDIR2,dirpath,'b0_NoiseHistSuperimposed.jpg');
    fig200name=strcat(MAINDIR2,dirpath,'SampleDWI_DiffRoiNoiseHist.jpg');
    fig300name=strcat(MAINDIR2,dirpath,'DWI_NoiseHistSuperimposed.jpg');
    fig400name=strcat(MAINDIR2,dirpath,'PLotsSNR_ALLdataAVESTD.jpg');
    fig450name=strcat(MAINDIR2,dirpath,'PLotsSNRNyq_eachb0.jpg');
    fig500name=strcat(MAINDIR2,dirpath,'PLotsSNR_eachDWI.jpg');  
    print('-f100','-djpeg',fig100name)
    print('-f150','-djpeg',fig150name)
    print('-f200','-djpeg',fig200name)
    print('-f300','-djpeg',fig300name)
    print('-f400','-djpeg',fig400name)
    if ynNyq=='y'
        print('-f450','-djpeg',fig450name)
    end
    print('-f500','-djpeg',fig500name)
    
    
    
     % print FA stuff
    fig11name=strcat(MAINDIR2,dirpath,'DxxDyyDzz.jpg');
    fig12name=strcat(MAINDIR2,dirpath,'ADC.jpg');
    fig13name=strcat(MAINDIR2,dirpath,'Eigvalues.jpg');
    fig14name=strcat(MAINDIR2,dirpath,'FAvalues.jpg');
    print('-f11','-djpeg',fig11name)
    print('-f12','-djpeg',fig12name)
    print('-f13','-djpeg',fig13name)
    print('-f14','-djpeg',fig14name)
    
 
    if ynNyq=='y'    
        for b=1:nb0
            figname=strcat(MAINDIR2,dirpath,'ImgNyqRatROIsMask_b0num',num2str(b),'.jpg');
            figstr=strcat('-f',num2str(20+b));
            print(figstr,'-djpeg',figname)
        end
    end

 

fclose all;

