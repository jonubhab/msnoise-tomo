def plot_FTAN_result(filename, basename, per, disper, diagramtype,save,show=True):
    # This function will plot the FTAN matrix and overlay the dispersion curve

    # get FTAN matrix
    amp = np.loadtxt('%s_amp.txt'%basename).T

    # Process the dispersion curve
    U = np.loadtxt('%s_TV.txt'%basename)
    P = np.loadtxt('%s_FP.txt'%basename)
    # get axes limits
    xmin = min(P)
    xmax = max(P)
    ymin = min(U)
    ymax = max(U)

    # setup matrix for contour plot
    Per, Vitg = np.meshgrid(P,U)
    plt.figure()
    plt.contourf(Per, Vitg, amp, 35, cmap=viridis)
    plt.colorbar()
    # plt.contour(Per, Vitg, amp, 35, colors='k')

    plt.plot(per, disper,'-ok',lw=1.5)
    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)

    # Set axes labels depending on diagramtype
    if diagramtype == 'PV':
        plt.xlabel("Period (s)")
        plt.ylabel("Velocity (km/s)")
    elif diagramtype == 'FV':
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Velocity (km/s)")
    elif diagramtype == 'FT':
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Time (s)")
    elif diagramtype == 'PT':
        plt.xlabel("Period (s)")
        plt.ylabel("Time (s)")

    NET1, STA1, NET2, STA2, crap = os.path.split(filename)[1].split('_')

    title="%s.%s - %s.%s"%(NET1, STA1, NET2, STA2)

    plt.title("FTAN\n"+title)

    os.makedirs(save, exist_ok=True) #
    plt.savefig(os.path.join(save,f"{title}.png")) #
    #plt.show()