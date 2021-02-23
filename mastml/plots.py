"""
This module contains a collection of functions which make plots (saved as png files) using matplotlib, generated from
some model fits and cross-validation evaluation within a MAST-ML run.

This module also contains a method to create python notebooks containing plotted data and the relevant source code from
this module, to enable the user to make their own modifications to the created plots in a straightforward way (useful for
tweaking plots for a presentation or publication).
"""

import math
import os
import pandas as pd
import numpy as np
from collections import Iterable, OrderedDict
from math import log, floor, ceil
from scipy.stats import gaussian_kde, norm
import scipy.stats as stats
import statistics

from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from mastml.metrics import Metrics
from mastml.error_analysis import ErrorUtils

import matplotlib
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure, figaspect
from matplotlib.font_manager import FontProperties
from mpl_toolkits.axes_grid1.inset_locator import mark_inset
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes
from mpl_toolkits.axes_grid1 import make_axes_locatable

matplotlib.rc('font', size=18, family='sans-serif') # set all font to bigger
matplotlib.rc('figure', autolayout=True) # turn on autolayout

import warnings
warnings.filterwarnings(action="ignore")

# adding dpi as a constant global so it can be changed later
DPI = 250

class Scatter():
    """
    Class to generate scatter plots, such as parity plots showing true vs. predicted data values

    Args:
        None

    Methods:

        plot_predicted_vs_true: method to plot a parity plot

            Args:

                y_true: (pd.Series), series of true y data

                y_pred: (pd.Series), series of predicted y data

                savepath: (str), string denoting the save path for the figure image

                file_name: (str), string denoting the character of the file name, e.g. train vs. test

                x_label: (str), string denoting the true and predicted property name

                metrics_list: (list), list of strings of metric names to evaluate and include on the figure

                groups: (pd.Series), series of group designations

                show_figure: (bool), whether or not to show the figure output (e.g. when using Jupyter notebook)

            Returns:
                None
    """
    @classmethod
    def plot_predicted_vs_true(cls, y_true, y_pred, savepath, file_name, data_type, x_label, metrics_list=None, groups=None, show_figure=False):
        # Make the dataframe/array 1D if it isn't
        y_true = check_dimensions(y_true)
        y_pred = check_dimensions(y_pred)

        # Set image aspect ratio:
        fig, ax = make_fig_ax()

        # gather max and min
        max1 = max(np.nanmax(y_true), np.nanmax(y_pred))
        min1 = min(np.nanmin(y_true), np.nanmin(y_pred))

        maxx = max(y_true)
        minn = min(y_true)
        maxx = round(float(maxx), rounder(maxx - minn))
        minn = round(float(minn), rounder(maxx - minn))
        _set_tick_labels(ax, maxx, minn)

        if groups is None:
            ax.scatter(y_true, y_pred, c='b', edgecolor='darkblue', zorder=2, s=100, alpha=0.7)
        else:
            colors = ['blue', 'red', 'green', 'purple', 'orange', 'black']
            markers = ['o', 'v', '^', 's', 'p', 'h', 'D', '*', 'X', '<', '>', 'P']
            colorcount = markercount = 0
            for groupcount, group in enumerate(np.unique(groups)):
                mask = groups == group
                ax.scatter(y_true[mask], y_pred[mask], label=group, color=colors[colorcount],
                           marker=markers[markercount], s=100, alpha=0.7)
                ax.legend(loc='lower right', fontsize=12)
                colorcount += 1
                if colorcount % len(colors) == 0:
                    markercount += 1
                    colorcount = 0

        # draw dashed horizontal line
        ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

        ax.set_xlabel('True '+ x_label, fontsize=14)
        ax.set_ylabel('Predicted ' + x_label, fontsize=14)

        if metrics_list is None:
            # Use some default metric set
            metrics_list = ['r2_score', 'mean_absolute_error', 'root_mean_squared_error', 'rmse_over_stdev']
        stats_dict = Metrics(metrics_list=metrics_list).evaluate(y_true=y_true, y_pred=y_pred)

        plot_stats(fig, stats_dict, x_align=0.65, y_align=0.90, fontsize=12)

        # Save data to excel file and image
        df = pd.DataFrame().from_dict(data={"y_true": y_true, "y_pred": y_pred})
        #df_stats = pd.DataFrame().from_records([stats_dict])
        #df.to_excel(os.path.join(savepath, file_name + '.xlsx'))
        #df_stats.to_excel(os.path.join(savepath, data_type + '_stats_summary.xlsx'), index=False)
        fig.savefig(os.path.join(savepath, file_name + '.png'), dpi=DPI, bbox_inches='tight')
        if show_figure == True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_best_worst_split(cls, savepath, data_type, x_label, metrics_list, show_figure=False):
        dirs = os.listdir(savepath)
        splitdirs = [d for d in dirs if 'split_' in d and '.png' not in d]

        stats_files_dict = dict()
        for splitdir in splitdirs:
            stats_files_dict[splitdir] = pd.read_excel(os.path.join(os.path.join(savepath, splitdir), data_type + '_stats_summary.xlsx')).to_dict('records')[0]

        # Find best/worst splits based on RMSE value
        rmse_best = 10**20
        rmse_worst = 0
        for split, stats_dict in stats_files_dict.items():
            if stats_dict['root_mean_squared_error'] < rmse_best:
                best_split = split
                rmse_best = stats_dict['root_mean_squared_error']
            if stats_dict['root_mean_squared_error'] > rmse_worst:
                worst_split = split
                rmse_worst = stats_dict['root_mean_squared_error']
        if data_type == 'test':
            y_true_best = pd.read_excel(os.path.join(os.path.join(savepath, best_split), 'y_test.xlsx'))
            y_pred_best = pd.read_excel(os.path.join(os.path.join(savepath, best_split), 'y_pred.xlsx'))
            y_true_worst = pd.read_excel(os.path.join(os.path.join(savepath, worst_split), 'y_test.xlsx'))
            y_pred_worst = pd.read_excel(os.path.join(os.path.join(savepath, worst_split), 'y_pred.xlsx'))
        elif data_type == 'train':
            y_true_best = pd.read_excel(os.path.join(os.path.join(savepath, best_split), 'y_train.xlsx'))
            y_pred_best = pd.read_excel(os.path.join(os.path.join(savepath, best_split), 'y_pred_train.xlsx'))
            y_true_worst = pd.read_excel(os.path.join(os.path.join(savepath, worst_split), 'y_train.xlsx'))
            y_pred_worst = pd.read_excel(os.path.join(os.path.join(savepath, worst_split), 'y_pred_train.xlsx'))

        # Make the dataframe/array 1D if it isn't
        y_true_best = check_dimensions(y_true_best)
        y_pred_best = check_dimensions(y_pred_best)
        y_true_worst = check_dimensions(y_true_worst)
        y_pred_worst = check_dimensions(y_pred_worst)

        # Set image aspect ratio:
        fig, ax = make_fig_ax()

        # gather max and min
        max1 = max(np.nanmax(y_true_best), np.nanmax(y_pred_best), np.nanmax(y_true_worst), np.nanmax(y_pred_worst))
        min1 = min(np.nanmin(y_true_best), np.nanmin(y_pred_best), np.nanmin(y_true_worst), np.nanmin(y_pred_worst))

        maxx = round(float(max1), rounder(max1 - min1))
        minn = round(float(min1), rounder(max1 - min1))
        _set_tick_labels(ax, maxx, minn)

        ax.scatter(y_true_best, y_pred_best, c='b', edgecolor='darkblue', zorder=2, s=100, alpha=0.7, label='Best split')
        ax.scatter(y_true_worst, y_pred_worst, c='r', edgecolor='darkred', zorder=2, s=100, alpha=0.7, label='Worst split')

        ax.legend(loc='best')

        # draw dashed horizontal line
        ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

        ax.set_xlabel('True '+ x_label, fontsize=14)
        ax.set_ylabel('Predicted ' + x_label, fontsize=14)

        stats_dict_best = Metrics(metrics_list=metrics_list).evaluate(y_true=y_true_best, y_pred=y_pred_best)
        stats_dict_worst = Metrics(metrics_list=metrics_list).evaluate(y_true=y_true_worst, y_pred=y_pred_worst)

        plot_stats(fig, stats_dict_best, x_align=0.65, y_align=0.90, font_dict={'fontsize':12, 'color':'blue'})
        plot_stats(fig, stats_dict_worst, x_align=0.65, y_align=0.50, font_dict={'fontsize': 12, 'color': 'red'})

        # Save data to excel file and image
        fig.savefig(os.path.join(savepath, 'parity_plot_best_worst_split_'+str(data_type)+'.png'), dpi=DPI, bbox_inches='tight')
        if show_figure == True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_best_worst_per_point(cls, savepath, data_type, x_label, metrics_list, show_figure=False):
        """
        Method to create a parity plot (predicted vs. true values) of the set of best and worst CV scores for each

        individual data point.

        Args:

            y_true: (numpy array), array of true y data

            y_pred_list: (list), list of numpy arrays containing predicted y data for each CV split

            savepath: (str), path to save plots to

            metrics_dict: (dict), dict of scikit-learn metric objects to calculate score of predicted vs. true values

            avg_stats: (dict), dict of calculated average metrics over all CV splits

            title: (str), title of the best_worst_per_point plot

            label: (str), label used for axis labeling

        Returns:

            None

        """

        # Get lists of all ytrue and ypred for each split
        dirs = os.listdir(savepath)
        splitdirs = [d for d in dirs if 'split_' in d and '.png' not in d]

        y_true_list = list()
        y_pred_list = list()
        for splitdir in splitdirs:
            y_true_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_'+str(data_type)+'.xlsx')))
            if data_type == 'test':
                y_pred_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_pred.xlsx')))
            elif data_type == 'train':
                y_pred_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_pred_train.xlsx')))

        all_y_true = list()
        all_y_pred = list()
        all_abs_residuals = list()
        for yt, y_pred in zip(y_true_list, y_pred_list):
            yt = np.array(check_dimensions(yt))
            y_pred = np.array(check_dimensions(y_pred))
            abs_residuals = abs(yt-y_pred)
            all_y_true.append(yt)
            all_y_pred.append(y_pred)
            all_abs_residuals.append(abs_residuals)
        all_y_true_flat = np.array([item for sublist in all_y_true for item in sublist])
        all_y_pred_flat = np.array([item for sublist in all_y_pred for item in sublist])
        all_residuals_flat = np.array([item for sublist in all_abs_residuals for item in sublist])

        y_true_unique = np.unique(all_y_true_flat)
        bests = list()
        worsts = list()
        for yt in y_true_unique:
            best = min(abs(all_y_pred_flat[np.where(all_y_true_flat==yt)] - all_y_true_flat[np.where(all_y_true_flat==yt)]))
            worst = max(abs(all_y_pred_flat[np.where(all_y_true_flat==yt)] - all_y_true_flat[np.where(all_y_true_flat==yt)]))
            bests.append(all_y_pred_flat[np.where(all_residuals_flat==best)])
            worsts.append(all_y_pred_flat[np.where(all_residuals_flat==worst)])

        stats_dict_best = Metrics(metrics_list=metrics_list).evaluate(y_true=y_true_unique, y_pred=bests)
        stats_dict_worst = Metrics(metrics_list=metrics_list).evaluate(y_true=y_true_unique, y_pred=worsts)

        fig, ax = make_fig_ax(x_align=0.65)

        # gather max and min
        max1 = max([max(y_true_unique), max(bests), max(worsts)])
        min1 = min([min(y_true_unique), min(bests), min(worsts)])

        # draw dashed horizontal line
        ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

        # set axis labels
        ax.set_xlabel('True '+x_label, fontsize=16)
        ax.set_ylabel('Predicted '+x_label, fontsize=16)

        # set tick labels
        maxx = round(float(max1), rounder(max1-min1))
        minn = round(float(min1), rounder(max1-min1))
        _set_tick_labels(ax, maxx, minn)

        ax.scatter(y_true_unique, bests,  c='b',  alpha=0.7, label='best all points', edgecolor='darkblue', zorder=2, s=100)
        ax.scatter(y_true_unique, worsts, c='r', alpha=0.7, label='worst all points', edgecolor='darkred', zorder=2, s=70)
        ax.legend(loc='best', fontsize=12)

        #plot_stats(fig, avg_stats, x_align=x_align, y_align=0.51, fontsize=10)
        plot_stats(fig, stats_dict_best, x_align=0.65, y_align=0.90, font_dict={'fontsize':10, 'color':'b'})
        plot_stats(fig, stats_dict_worst, x_align=0.65, y_align=0.50, font_dict={'fontsize':10, 'color':'r'})

        # Save data to excel file and image
        fig.savefig(os.path.join(savepath, 'parity_plot_best_worst_eachpoint_'+str(data_type)+'.png'), dpi=DPI, bbox_inches='tight')
        if show_figure == True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_predicted_vs_true_bars(cls, savepath, x_label, data_type, metrics_list, groups=None, show_figure=False):
        """
        Method to calculate parity plot (predicted vs. true) of average predictions, averaged over all CV splits, with error

        bars on each point corresponding to the standard deviation of the predicted values over all CV splits.

        Args:

            y_true: (numpy array), array of true y data

            y_pred_list: (list), list of numpy arrays containing predicted y data for each CV split

            avg_stats: (dict), dict of calculated average metrics over all CV splits

            savepath: (str), path to save plots to

            title: (str), title of the best_worst_per_point plot

            label: (str), label used for axis labeling

        Returns:

            None

        """

        # Get lists of all ytrue and ypred for each split
        dirs = os.listdir(savepath)
        splitdirs = [d for d in dirs if 'split_' in d and '.png' not in d]

        y_true_list = list()
        y_pred_list = list()
        for splitdir in splitdirs:
            y_true_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_'+str(data_type)+'.xlsx')))
            if data_type == 'test':
                y_pred_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_pred.xlsx')))
            elif data_type == 'train':
                y_pred_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_pred_train.xlsx')))
            elif data_type == 'leaveout':
                y_pred_list.append(pd.read_excel(os.path.join(os.path.join(savepath, splitdir), 'y_pred_leaveout.xlsx')))

        all_y_true = list()
        all_y_pred = list()
        for yt, y_pred in zip(y_true_list, y_pred_list):
            yt = np.array(check_dimensions(yt))
            y_pred = np.array(check_dimensions(y_pred))
            all_y_true.append(yt)
            all_y_pred.append(y_pred)

        df_all = pd.DataFrame({'all_y_true': np.array([item for sublist in all_y_true for item in sublist]),
                            'all_y_pred': np.array([item for sublist in all_y_pred for item in sublist])})

        df_all_grouped = df_all.groupby(df_all['all_y_true'], sort=False)
        df_avg = df_all_grouped.mean()
        df_std = df_all_grouped.std()

        # make fig and ax, use x_align when placing text so things don't overlap
        x_align = 0.64
        fig, ax = make_fig_ax(x_align=x_align)

        # gather max and min
        max1 = max(np.nanmax(df_avg.index.values.tolist()), np.nanmax(df_avg['all_y_pred']))
        min1 = min(np.nanmin(df_avg.index.values.tolist()), np.nanmin(df_avg['all_y_pred']))

        # draw dashed horizontal line
        ax.plot([min1, max1], [min1, max1], 'k--', lw=2, zorder=1)

        # set axis labels
        ax.set_xlabel('True ' + x_label, fontsize=16)
        ax.set_ylabel('Predicted ' + x_label, fontsize=16)

        # set tick labels
        _set_tick_labels(ax, max1, min1)

        if groups is None:
            ax.errorbar(df_avg.index.values.tolist(), df_avg['all_y_pred'], yerr=df_std['all_y_pred'], fmt='o', markerfacecolor='blue', markeredgecolor='black',
                        markersize=10, alpha=0.7, capsize=3)
        else:
            colors = ['blue', 'red', 'green', 'purple', 'orange', 'black']
            markers = ['o', 'v', '^', 's', 'p', 'h', 'D', '*', 'X', '<', '>', 'P']
            colorcount = markercount = 0
            handles = dict()
            unique_groups = np.unique(groups)
            for groupcount, group in enumerate(unique_groups):
                mask = groups == group
                handles[group] = ax.errorbar(df_avg.index.values.tolist()[mask], df_avg['all_y_pred'][mask], yerr=df_std['all_y_pred'][mask],
                                             marker=markers[markercount], markerfacecolor=colors[colorcount],
                                             markeredgecolor=colors[colorcount], ecolor=colors[colorcount],
                                             markersize=10, alpha=0.7, capsize=3, fmt='o')
                colorcount += 1
                if colorcount % len(colors) == 0:
                    markercount += 1
                    colorcount = 0
            ax.legend(handles.values(), handles.keys(), loc='best', fontsize=10)

        avg_stats = Metrics(metrics_list=metrics_list).evaluate(y_true=df_avg.index.values.tolist(), y_pred=df_avg['all_y_pred'])
        plot_stats(fig, avg_stats, x_align=x_align, y_align=0.90)

        fig.savefig(os.path.join(savepath, 'parity_plot_allsplits_average.png'), dpi=DPI, bbox_inches='tight')

        df = pd.DataFrame({'y true': df_avg.index.values.tolist(),
                           'average predicted values': df_avg['all_y_pred'],
                           'error bar values': df_std['all_y_pred']})
        df.to_excel(os.path.join(savepath, 'parity_plot_allsplits_average.xlsx'))
        if show_figure == True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_metric_vs_group(cls, savepath, data_type, show_figure):
        """
        Method to plot the value of a particular calculated metric (e.g. RMSE, R^2, etc) for each data group

        Args:

            savepath: (str), path to save plots to

            data_type: (str), 'test' or 'train' to denote data type

        Returns:

            None

        """
        dirs = os.listdir(savepath)
        splitdirs = [d for d in dirs if 'split_' in d and '.png' not in d]

        stats_files_dict = dict()
        groups = list()
        for splitdir in splitdirs:
            with open(os.path.join(os.path.join(savepath, splitdir), 'test_group.txt'), 'r') as f:
                group = f.readlines()[0]
                groups.append(group)
            stats_files_dict[group] = pd.read_excel(os.path.join(os.path.join(savepath, splitdir), data_type + '_stats_summary.xlsx')).to_dict('records')[0]
            metrics_list = list(stats_files_dict[group].keys())

        for metric in metrics_list:
            stats = list()
            for group in groups:
                stats.append(stats_files_dict[group][metric])

            avg_stats = {metric : (np.mean(stats), np.std(stats))}

            # make fig and ax, use x_align when placing text so things don't overlap
            x_align = 0.64
            fig, ax = make_fig_ax(x_align=x_align)

            # do the actual plotting
            ax.scatter(groups, stats, c='blue', alpha=0.7, edgecolor='darkblue', zorder=2, s=100)

            # set axis labels
            ax.set_xlabel('Group', fontsize=14)
            ax.set_ylabel(metric, fontsize=14)
            ax.set_xticklabels(labels=groups, fontsize=14)
            plot_stats(fig, avg_stats, x_align=x_align, y_align=0.90)

            fig.savefig(os.path.join(savepath, str(metric)+'_value_per_group_'+str(data_type)+'.png'), dpi=DPI, bbox_inches='tight')
            if show_figure == True:
                plt.show()
            else:
                plt.close()
        return

class Error():
    '''

    '''
    @classmethod
    def plot_normalized_error(cls, residuals, savepath, data_type, model_errors=None, show_figure=False):
        """
        Method to plot the normalized residual errors of a model prediction

        Args:

            y_true: (numpy array), array containing the true y data values

            y_pred: (numpy array), array containing the predicted y data values

            savepath: (str), path to save the plotted normalized error plot

            model: (scikit-learn model/estimator object), a scikit-learn model object

            X: (numpy array), array of X features

            avg_stats: (dict), dict of calculated average metrics over all CV splits

        Returns:

            None

        """

        x_align = 0.64
        fig, ax = make_fig_ax(x_align=x_align)
        mu = 0
        sigma = 1
        residuals[residuals==0.0] = 10**-6
        normalized_residuals = residuals / np.std(residuals)
        density_residuals = gaussian_kde(normalized_residuals)
        x = np.linspace(mu - 5 * sigma, mu + 5 * sigma, residuals.shape[0])
        ax.plot(x, norm.pdf(x, mu, sigma), linewidth=4, color='blue', label="Analytical Gaussian")
        ax.plot(x, density_residuals(x), linewidth=4, color='green', label="Model Residuals")
        maxx = 5
        minn = -5

        if model_errors is not None:
            model_errors[model_errors == 0.0] = 0.0001
            rstat = residuals / model_errors
            density_errors = gaussian_kde(rstat)
            maxy = max(max(density_residuals(x)), max(norm.pdf(x, mu, sigma)), max(density_errors(x)))
            miny = min(min(density_residuals(x)), min(norm.pdf(x, mu, sigma)), max(density_errors(x)))
            ax.plot(x, density_errors(x), linewidth=4, color='purple', label="Model Errors")
            # Save data to csv file
            data_dict = {"Plotted x values": x, "model_errors": model_errors,
                         #"analytical gaussian (plotted y blue values)": norm.pdf(x, mu, sigma),
                         "residuals": residuals,
                         "model normalized residuals (plotted y green values)": density_residuals(x),
                         "model errors (plotted y purple values)": density_errors(x)}
            pd.DataFrame(data_dict).to_excel(os.path.join(savepath, 'normalized_error_data_'+str(data_type)+'.xlsx'))
        else:
            # Save data to csv file
            data_dict = {"x values": x,
                         #"analytical gaussian": norm.pdf(x, mu, sigma),
                         "model normalized residuals (plotted y green values)": density_residuals(x)}
            pd.DataFrame(data_dict).to_excel(os.path.join(savepath, 'normalized_error_data_'+str(data_type)+'.xlsx'))
            maxy = max(max(density_residuals(x)), max(norm.pdf(x, mu, sigma)))
            miny = min(min(density_residuals(x)), min(norm.pdf(x, mu, sigma)))

        ax.legend(loc=0, fontsize=12, frameon=False)
        ax.set_xlabel(r"$\mathrm{x}/\mathit{\sigma}$", fontsize=18)
        ax.set_ylabel("Probability density", fontsize=18)
        _set_tick_labels_different(ax, maxx, minn, maxy, miny)
        fig.savefig(os.path.join(savepath, 'normalized_errors_'+str(data_type)+'.png'), dpi=DPI, bbox_inches='tight')
        if show_figure is True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_cumulative_normalized_error(cls, residuals, savepath, data_type, model_errors=None, show_figure=False):
        """
        Method to plot the cumulative normalized residual errors of a model prediction

        Args:

            y_true: (numpy array), array containing the true y data values

            y_pred: (numpy array), array containing the predicted y data values

            savepath: (str), path to save the plotted cumulative normalized error plot

            model: (scikit-learn model/estimator object), a scikit-learn model object

            X: (numpy array), array of X features

            avg_stats: (dict), dict of calculated average metrics over all CV splits

        Returns:

            None

        """

        x_align = 0.64
        fig, ax = make_fig_ax(x_align=x_align)

        analytic_gau = np.random.normal(0, 1, 10000)
        analytic_gau = abs(analytic_gau)
        n_analytic = np.arange(1, len(analytic_gau) + 1) / np.float(len(analytic_gau))
        X_analytic = np.sort(analytic_gau)
        residuals[residuals == 0.0] = 10 ** -6
        normalized_residuals = abs((residuals) / np.std(residuals))
        n_residuals = np.arange(1, len(normalized_residuals) + 1) / np.float(len(normalized_residuals))
        X_residuals = np.sort(normalized_residuals)  # r"$\mathrm{Predicted \/ Value}, \mathit{eV}$"
        ax.set_xlabel(r"$\mathrm{x}/\mathit{\sigma}$", fontsize=18)
        ax.set_ylabel("Fraction", fontsize=18)
        ax.step(X_residuals, n_residuals, linewidth=3, color='green', label="Model Residuals")
        ax.step(X_analytic, n_analytic, linewidth=3, color='blue', label="Analytical Gaussian")
        ax.set_xlim([0, 5])

        if model_errors is not None:
            model_errors[model_errors == 0.0] = 0.0001
            rstat = abs((residuals) / model_errors)
            n_errors = np.arange(1, len(rstat) + 1) / np.float(len(rstat))
            X_errors = np.sort(rstat)
            ax.step(X_errors, n_errors, linewidth=3, color='purple', label="Model Errors")
            # Save data to csv file
            data_dict = { #"Analytical Gaussian values": analytic_gau,
                         #"Analytical Gaussian (sorted, blue data)": X_analytic,
                         "residuals": residuals,
                         "normalized residuals": normalized_residuals,
                         "Model Residuals (sorted, green data)": X_residuals,
                         "Model error values (r value: (ytrue-ypred)/(model error avg))": rstat,
                         "Model errors (sorted, purple values)": X_errors}
            # Save this way to avoid issue with different array sizes in data_dict
            df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in data_dict.items()]))
            df.to_excel(os.path.join(savepath, 'cumulative_normalized_errors_'+str(data_type)+'.xlsx'), index=False)
        else:
            # Save data to csv file
            data_dict = {#"x analytical": X_analytic,
                         #"analytical gaussian": n_analytic,
                          "Model Residuals (sorted, green data)": X_residuals,
                         "model residuals": n_residuals}
            # Save this way to avoid issue with different array sizes in data_dict
            df = pd.DataFrame(dict([ (k, pd.Series(v)) for k,v in data_dict.items() ]))
            df.to_excel(os.path.join(savepath, 'cumulative_normalized_errors_'+str(data_type)+'.xlsx'), index=False)

        ax.legend(loc=0, fontsize=14, frameon=False)
        xlabels = np.linspace(2, 3, 3)
        ylabels = np.linspace(0.9, 1, 2)
        axin = zoomed_inset_axes(ax, 2.5, loc=7)
        axin.step(X_residuals, n_residuals, linewidth=3, color='green', label="Model Residuals")
        axin.step(X_analytic, n_analytic, linewidth=3, color='blue', label="Analytical Gaussian")
        if model_errors is not None:
            axin.step(X_errors, n_errors, linewidth=3, color='purple', label="Model Errors")
        axin.set_xticklabels(xlabels, fontsize=8, rotation=90)
        axin.set_yticklabels(ylabels, fontsize=8)
        axin.set_xlim([2, 3])
        axin.set_ylim([0.9, 1])

        maxx = 5
        minn = 0
        maxy = 1.1
        miny = 0
        _set_tick_labels_different(ax, maxx, minn, maxy, miny)

        mark_inset(ax, axin, loc1=1, loc2=2)
        fig.savefig(os.path.join(savepath, 'cumulative_normalized_errors_'+str(data_type)+'.png'), dpi=DPI, bbox_inches='tight')
        if show_figure is True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_rstat(cls, savepath, data_type, residuals, model_errors, show_figure=False, is_calibrated=False):

        #if recalibrate_errors == True:
        #    if len(recalibrate_dict.keys()) == 0:
        #        model_errors, a, b = ErrorUtils()._recalibrate_errors(model_errors, residuals)
        #    else:
        #        a = recalibrate_dict['a']
        #        b = recalibrate_dict['b']
        #        model_errors = a*np.array(model_errors) + b

        # Eliminate model errors with value 0, so that the ratios can be calculated
        zero_indices = []
        for i in range(0, len(model_errors)):
            if model_errors[i] == 0:
                zero_indices.append(i)
        residuals = np.delete(residuals, zero_indices)
        model_errors = np.delete(model_errors, zero_indices)
        # make data for gaussian plot
        gaussian_x = np.linspace(-5, 5, 1000)
        # create plot
        x_align = 0.64
        fig, ax = make_fig_ax(x_align=x_align)
        ax.set_xlabel('residuals / model error estimates')
        ax.set_ylabel('relative counts')
        ax.hist(residuals/model_errors, bins=30, color='blue', edgecolor='black', density=True)
        ax.plot(gaussian_x, stats.norm.pdf(gaussian_x, 0, 1), label='Gaussian mu: 0 std: 1', color='orange')
        ax.text(0.05, 0.9, 'mean = %.3f' % (np.mean(residuals / model_errors)), transform=ax.transAxes)
        ax.text(0.05, 0.85, 'std = %.3f' % (np.std(residuals / model_errors)), transform=ax.transAxes)

        if is_calibrated == False:
            calibrate = 'uncalibrated'
        if is_calibrated == True:
            calibrate = 'calibrated'

        fig.savefig(os.path.join(savepath, 'rstat_histogram_'+str(data_type)+'_'+calibrate+'.png'), dpi=DPI, bbox_inches='tight')

        if show_figure is True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_rstat_uncal_cal_overlay(cls, savepath, data_type, residuals, model_errors, model_errors_cal,
                                     show_figure=False):

        #model_errors_uncal = model_errors
        #if len(recalibrate_dict.keys()) == 0:
        #    model_errors_cal, a, b = ErrorUtils()._recalibrate_errors(model_errors=model_errors, residuals=residuals)
        #else:
        #    a = recalibrate_dict['a']
        #    b = recalibrate_dict['b']
        #    model_errors_cal = a*np.array(model_errors_uncal) + b

        # Write the recalibration values to file
        #recal_df = pd.DataFrame({'slope (a)': a, 'intercept (b)': b}, index=[0])
        #recal_df.to_excel(os.path.join(savepath, 'recalibration_parameters_'+str(data_type)+'.xlsx'), index=False)

        # Write the calibrated model errors to file
        #df = pd.Series(model_errors_cal, name='model_errors')
        #df.to_excel(os.path.join(savepath, 'model_errors_'+str(data_type)+'_calibrated') + '.xlsx', index=False)

        # Eliminate model errors with value 0, so that the ratios can be calculated
        zero_indices = []
        for i in range(0, len(model_errors)):
            if model_errors[i] == 0:
                zero_indices.append(i)
        residuals = np.delete(residuals, zero_indices)
        model_errors = np.delete(model_errors, zero_indices)
        model_errors_cal = np.delete(model_errors_cal, zero_indices)

        # make data for gaussian plot
        gaussian_x = np.linspace(-5, 5, 1000)
        # create plot
        x_align = 0.64
        fig, ax = make_fig_ax(x_align=x_align)
        ax.set_xlabel('residuals / model error estimates')
        ax.set_ylabel('relative counts')
        ax.hist(residuals/model_errors, bins=30, color='gray', edgecolor='black', density=True, alpha=0.4)
        ax.hist(residuals/model_errors_cal, bins=30, color='blue', edgecolor='black', density=True, alpha=0.4)
        ax.plot(gaussian_x, stats.norm.pdf(gaussian_x, 0, 1), label='Gaussian mu: 0 std: 1', color='orange')
        ax.text(0.05, 0.9, 'mean = %.3f' % (np.mean(residuals / model_errors)), transform=ax.transAxes, fontdict={'fontsize':10, 'color':'gray'})
        ax.text(0.05, 0.85, 'std = %.3f' % (np.std(residuals / model_errors)), transform=ax.transAxes, fontdict={'fontsize':10, 'color':'gray'})
        ax.text(0.05, 0.8, 'mean = %.3f' % (np.mean(residuals / model_errors_cal)), transform=ax.transAxes, fontdict={'fontsize':10, 'color':'blue'})
        ax.text(0.05, 0.75, 'std = %.3f' % (np.std(residuals / model_errors_cal)), transform=ax.transAxes, fontdict={'fontsize':10, 'color':'blue'})
        fig.savefig(os.path.join(savepath, 'rstat_histogram_'+str(data_type)+'_uncal_cal_overlay.png'), dpi=DPI, bbox_inches='tight')

        if show_figure is True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_real_vs_predicted_error(cls, savepath, model, data_type, model_errors, residuals, dataset_stdev,
                                     show_figure=False, is_calibrated=False, well_sampled_fraction=0.025):

        bin_values, rms_residual_values, num_values_per_bin, number_of_bins = ErrorUtils()._parse_error_data(model_errors=model_errors,
                                                                                                            residuals=residuals,
                                                                                                            dataset_stdev=dataset_stdev)

        model_name = model.model.__class__.__name__
        if model_name == 'RandomForestRegressor':
            model_type = 'RF'
        elif model_name == 'GradientBoostingRegressor':
            model_type = 'GBR'
        elif model_name == 'ExtraTreesRegressor':
            model_type = 'ET'
        elif model_name == 'GaussianProcessRegressor':
            model_type = 'GPR'
        elif model_name == 'BaggingRegressor':
            model_type = 'BR'

        if data_type not in ['train', 'test', 'leaveout']:
            print('Error: data_test_type must be one of "train", "test" or "leaveout"')
            exit()

        # Make RF error plot
        fig, ax = make_fig_ax(aspect_ratio=0.5, x_align=0.65)

        linear = LinearRegression(fit_intercept=True)
        # Fit just blue circle data
        # Find nan entries
        nans = np.argwhere(np.isnan(rms_residual_values)).tolist()

        # use nans (which are indices) to delete relevant parts of bin_values and
        # rms_residual_values as they can't be used to fit anyway
        bin_values_copy = np.empty_like(bin_values)
        bin_values_copy[:] = bin_values
        rms_residual_values_copy = np.empty_like(rms_residual_values)
        rms_residual_values_copy[:] = rms_residual_values
        bin_values_copy = np.delete(bin_values_copy, nans)
        rms_residual_values_copy = np.delete(rms_residual_values_copy, nans)

        num_values_per_bin_copy = np.array(num_values_per_bin)[np.array(num_values_per_bin) != 0]

        # Only examine the bins that are well-sampled, i.e. have number of data points in them above a given threshold
        well_sampled_number = round(well_sampled_fraction*np.sum(num_values_per_bin_copy))
        rms_residual_values_wellsampled = rms_residual_values_copy[np.where(num_values_per_bin_copy > well_sampled_number)]
        bin_values_wellsampled = bin_values_copy[np.where(num_values_per_bin_copy>well_sampled_number)]
        num_values_per_bin_wellsampled = num_values_per_bin_copy[np.where(num_values_per_bin_copy>well_sampled_number)]
        rms_residual_values_poorlysampled = rms_residual_values_copy[np.where(num_values_per_bin_copy <= well_sampled_number)]
        bin_values_poorlysampled = bin_values_copy[np.where(num_values_per_bin_copy<=well_sampled_number)]
        num_values_per_bin_poorlysampled = num_values_per_bin_copy[np.where(num_values_per_bin_copy<=well_sampled_number)]

        ax.scatter(bin_values_wellsampled, rms_residual_values_wellsampled, s=80, color='blue', alpha=0.7)
        ax.scatter(bin_values_poorlysampled, rms_residual_values_poorlysampled, s=80, edgecolor='blue', alpha=0.7)

        ax.set_xlabel(str(model_type) + ' model errors / dataset stdev', fontsize=12)
        ax.set_ylabel('RMS Absolute residuals\n / dataset stdev', fontsize=12)
        ax.tick_params(labelsize=10)

        if not rms_residual_values_copy.size:
            print("---WARNING: ALL ERRORS TOO LARGE FOR PLOTTING---")
            exit()
        else:
            # Fit the line to all data, including the poorly sampled data, and weight data points by number of samples per bin
            linear.fit(np.array(bin_values_copy).reshape(-1, 1), rms_residual_values_copy,
                       sample_weight=num_values_per_bin_copy)
            yfit = linear.predict(np.array(bin_values_copy).reshape(-1, 1))
            ax.plot(bin_values_copy, yfit, 'k--', linewidth=2)
            r2 = r2_score(rms_residual_values_copy, yfit, sample_weight=num_values_per_bin_copy)

            slope = linear.coef_
            intercept = linear.intercept_

        divider = make_axes_locatable(ax)
        axbarx = divider.append_axes("top", 1.2, pad=0.12, sharex=ax)

        axbarx.bar(x=bin_values, height=num_values_per_bin, width=bin_values[1]-bin_values[0], color='blue', edgecolor='black', alpha=0.7)
        axbarx.tick_params(labelsize=10, axis='y')
        axbarx.tick_params(labelsize=0, axis='x')
        axbarx.set_ylabel('Counts', fontsize=12)

        total_samples = sum(num_values_per_bin)
        axbarx.text(0.95, round(0.67 * max(num_values_per_bin)), 'Total counts = ' + str(total_samples), fontsize=12)

        xmax = max(max(bin_values_copy) + 0.05, 1.6)
        ymax = max(1.3, max(rms_residual_values))
        ax.set_ylim(bottom=0, top=ymax)
        axbarx.set_ylim(bottom=0, top=max(num_values_per_bin) + 50)
        ax.set_xlim(left=0, right=xmax)

        ax.text(0.02, 0.9*ymax, 'R$^2$ = %3.2f ' % r2, fontdict={'fontsize': 10, 'color': 'k'})
        ax.text(0.02, 0.8*ymax, 'slope = %3.2f ' % slope, fontdict={'fontsize': 10, 'color': 'k'})
        ax.text(0.02, 0.7*ymax, 'intercept = %3.2f ' % intercept, fontdict={'fontsize': 10, 'color': 'k'})

        # Plot y = x line as reference point
        maxx = max(xmax, ymax)
        ax.plot([0, maxx], [0, maxx], 'k--', lw=2, zorder=1, color='gray', alpha=0.5)

        if is_calibrated == False:
            calibrate = 'uncalibrated'
        if is_calibrated == True:
            calibrate = 'calibrated'

        fig.savefig(os.path.join(savepath, str(model_type) + '_residuals_vs_modelerror_' + str(data_type) + '_' + calibrate + '.png'),
            dpi=300, bbox_inches='tight')

        if show_figure is True:
            plt.show()
        else:
            plt.close()

        return

    @classmethod
    def plot_real_vs_predicted_error_uncal_cal_overlay(cls, savepath, model, data_type, model_errors, model_errors_cal,
                                                       residuals, dataset_stdev, show_figure=False,
                                                       well_sampled_fraction=0.025):

        bin_values_uncal, rms_residual_values_uncal, num_values_per_bin_uncal, number_of_bins_uncal = ErrorUtils()._parse_error_data(model_errors=model_errors,
                                                                                                                   residuals=residuals,
                                                                                                                   dataset_stdev=dataset_stdev)

        bin_values_cal, rms_residual_values_cal, num_values_per_bin_cal, number_of_bins_cal = ErrorUtils()._parse_error_data(model_errors=model_errors_cal,
                                                                                                                   residuals=residuals,
                                                                                                                   dataset_stdev=dataset_stdev)


        model_name = model.model.__class__.__name__
        if model_name == 'RandomForestRegressor':
            model_type = 'RF'
        elif model_name == 'GradientBoostingRegressor':
            model_type = 'GBR'
        elif model_name == 'ExtraTreesRegressor':
            model_type = 'ET'
        elif model_name == 'GaussianProcessRegressor':
            model_type = 'GPR'
        elif model_name == 'BaggingRegressor':
            model_type = 'BR'

        if data_type not in ['train', 'test', 'leaveout']:
            print('Error: data_test_type must be one of "train", "test" or "leaveout"')
            exit()

        # Make RF error plot
        fig, ax = make_fig_ax(aspect_ratio=0.5, x_align=0.65)

        linear_uncal = LinearRegression(fit_intercept=True)
        linear_cal = LinearRegression(fit_intercept=True)

        # Only examine the bins that are well-sampled, i.e. have number of data points in them above a given threshold
        well_sampled_number_uncal = round(well_sampled_fraction*np.sum(num_values_per_bin_uncal))
        rms_residual_values_wellsampled_uncal = rms_residual_values_uncal[np.where(num_values_per_bin_uncal > well_sampled_number_uncal)[0]]
        bin_values_wellsampled_uncal = bin_values_uncal[np.where(num_values_per_bin_uncal>well_sampled_number_uncal)[0]]
        num_values_per_bin_wellsampled_uncal = num_values_per_bin_uncal[np.where(num_values_per_bin_uncal>well_sampled_number_uncal)[0]]
        rms_residual_values_poorlysampled_uncal = rms_residual_values_uncal[np.where(num_values_per_bin_uncal <= well_sampled_number_uncal)[0]]
        bin_values_poorlysampled_uncal = bin_values_uncal[np.where(num_values_per_bin_uncal<=well_sampled_number_uncal)[0]]
        num_values_per_bin_poorlysampled_uncal = num_values_per_bin_uncal[np.where(num_values_per_bin_uncal<=well_sampled_number_uncal)[0]]

        well_sampled_number_cal = round(well_sampled_fraction*np.sum(num_values_per_bin_cal))
        rms_residual_values_wellsampled_cal = rms_residual_values_cal[np.where(num_values_per_bin_cal > well_sampled_number_cal)[0]]
        bin_values_wellsampled_cal = bin_values_cal[np.where(num_values_per_bin_cal>well_sampled_number_cal)]
        num_values_per_bin_wellsampled_cal = num_values_per_bin_cal[np.where(num_values_per_bin_cal>well_sampled_number_cal)[0]]
        rms_residual_values_poorlysampled_cal = rms_residual_values_cal[np.where(num_values_per_bin_cal <= well_sampled_number_cal)[0]]
        bin_values_poorlysampled_cal = bin_values_cal[np.where(num_values_per_bin_cal<=well_sampled_number_cal)[0]]
        num_values_per_bin_poorlysampled_cal = num_values_per_bin_cal[np.where(num_values_per_bin_cal<=well_sampled_number_cal)[0]]

        ax.scatter(bin_values_wellsampled_uncal, rms_residual_values_wellsampled_uncal, s=80, color='gray', edgecolor='gray', alpha=0.7, label='uncalibrated')
        ax.scatter(bin_values_poorlysampled_uncal, rms_residual_values_poorlysampled_uncal, s=80, color='gray', edgecolor='gray', alpha=0.3)

        ax.scatter(bin_values_wellsampled_cal, rms_residual_values_wellsampled_cal, s=80, color='blue', edgecolor='blue', alpha=0.7, label='calibrated')
        ax.scatter(bin_values_poorlysampled_cal, rms_residual_values_poorlysampled_cal, s=80, color='blue', edgecolor='blue', alpha=0.3)

        ax.set_xlabel(str(model_type) + ' model errors / dataset stdev', fontsize=12)
        ax.set_ylabel('RMS Absolute residuals\n / dataset stdev', fontsize=12)
        ax.tick_params(labelsize=10)

        # Fit the line to all data, including the poorly sampled data, and weight data points by number of samples per bin
        linear_uncal.fit(np.array(bin_values_uncal).reshape(-1, 1), rms_residual_values_uncal,
                       sample_weight=num_values_per_bin_uncal)
        yfit_uncal = linear_uncal.predict(np.array(bin_values_uncal).reshape(-1, 1))
        ax.plot(bin_values_uncal, yfit_uncal, 'gray', linewidth=2)
        r2_uncal = r2_score(rms_residual_values_uncal, yfit_uncal, sample_weight=num_values_per_bin_uncal)

        slope_uncal = linear_uncal.coef_
        intercept_uncal = linear_uncal.intercept_

        # Fit the line to all data, including the poorly sampled data, and weight data points by number of samples per bin
        linear_cal.fit(np.array(bin_values_cal).reshape(-1, 1), rms_residual_values_cal,
                       sample_weight=num_values_per_bin_cal)
        yfit_cal = linear_cal.predict(np.array(bin_values_cal).reshape(-1, 1))
        ax.plot(bin_values_cal, yfit_cal, 'blue', linewidth=2)
        r2_cal = r2_score(rms_residual_values_cal, yfit_cal, sample_weight=num_values_per_bin_cal)

        slope_cal = linear_cal.coef_
        intercept_cal = linear_cal.intercept_

        divider = make_axes_locatable(ax)
        axbarx = divider.append_axes("top", 1.2, pad=0.12, sharex=ax)

        axbarx.bar(x=bin_values_uncal, height=num_values_per_bin_uncal, width=bin_values_uncal[1]-bin_values_uncal[0],
                   color='gray', edgecolor='gray', alpha=0.3)
        axbarx.bar(x=bin_values_cal, height=num_values_per_bin_cal, width=bin_values_cal[1] - bin_values_cal[0],
                   color='blue', edgecolor='blue', alpha=0.3)
        axbarx.tick_params(labelsize=10, axis='y')
        axbarx.tick_params(labelsize=0, axis='x')
        axbarx.set_ylabel('Counts', fontsize=12)

        xmax = max(max(bin_values_uncal) + 0.05, 1.6)
        ymax = max(1.3, max(rms_residual_values_uncal))
        ax.set_ylim(bottom=0, top=ymax)
        axbarx.set_ylim(bottom=0, top=max(num_values_per_bin_uncal) + 50)
        ax.set_xlim(left=0, right=xmax)

        ax.text(0.02, 0.9*ymax, 'R$^2$ = %3.2f ' % r2_uncal, fontdict={'fontsize': 8, 'color': 'gray'})
        ax.text(0.02, 0.8*ymax, 'slope = %3.2f ' % slope_uncal, fontdict={'fontsize': 8, 'color': 'gray'})
        ax.text(0.02, 0.7*ymax, 'intercept = %3.2f ' % intercept_uncal, fontdict={'fontsize': 8, 'color': 'gray'})
        ax.text(0.02, 0.6*ymax, 'R$^2$ = %3.2f ' % r2_cal, fontdict={'fontsize': 8, 'color': 'blue'})
        ax.text(0.02, 0.5*ymax, 'slope = %3.2f ' % slope_cal, fontdict={'fontsize': 8, 'color': 'blue'})
        ax.text(0.02, 0.4*ymax, 'intercept = %3.2f ' % intercept_cal, fontdict={'fontsize': 8, 'color': 'blue'})

        # Plot y = x line as reference point
        maxx = max(xmax, ymax)
        ax.plot([0, maxx], [0, maxx], 'k--', lw=2, color='red', alpha=0.5)

        ax.legend(loc='lower right', fontsize=8)

        fig.savefig(os.path.join(savepath, str(model_type) + '_residuals_vs_modelerror_' + str(data_type) + '_uncal_cal_overlay.png'),
            dpi=300, bbox_inches='tight')

        if show_figure is True:
            plt.show()
        else:
            plt.close()

        return

class Histogram():
    """
    Class to generate histogram plots, such as histograms of residual values

    Args:
        None

    Methods:

        plot_histogram: method to plot a basic histogram of supplied data

            Args:

                df: (pd.DataFrame), dataframe or series of data to plot as a histogram

                savepath: (str), string denoting the save path for the figure image

                file_name: (str), string denoting the character of the file name, e.g. train vs. test

                x_label: (str), string denoting the  property name

                show_figure: (bool), whether or not to show the figure output (e.g. when using Jupyter notebook)

            Returns:
                None

        plot_residuals_histogram: method to plot a histogram of residual values

            Args:

                y_true: (pd.Series), series of true y data

                y_pred: (pd.Series), series of predicted y data

                savepath: (str), string denoting the save path for the figure image

                file_name: (str), string denoting the character of the file name, e.g. train vs. test

                show_figure: (bool), whether or not to show the figure output (e.g. when using Jupyter notebook)

            Returns:
                None

        _get_histogram_bins: Method to obtain the number of bins to use when plotting a histogram

            Args:

                df: (pandas Series or numpy array), array of y data used to construct histogram

            Returns:

                num_bins: (int), the number of bins to use when plotting a histogram
    """
    @classmethod
    def plot_histogram(cls, df, savepath, file_name, x_label, show_figure=False):
        # Make the dataframe 1D if it isn't
        df = check_dimensions(df)

        # make fig and ax, use x_align when placing text so things don't overlap
        x_align = 0.70
        fig, ax = make_fig_ax(aspect_ratio=0.5, x_align=x_align)

        #Get num_bins using smarter method
        num_bins = cls._get_histogram_bins(df=df)

        # do the actual plotting
        ax.hist(df, bins=num_bins, color='b', edgecolor='k')

        # normal text stuff
        ax.set_xlabel(x_label, fontsize=14)
        ax.set_ylabel('Number of occurrences', fontsize=14)

        plot_stats(fig, dict(df.describe()), x_align=x_align, y_align=0.90, fontsize=12)

        # Save data to excel file and image
        df.to_excel(os.path.join(savepath, file_name + '.xlsx'))
        df.describe().to_excel(os.path.join(savepath, file_name + '_statistics.xlsx'))
        fig.savefig(os.path.join(savepath, file_name + '.png'), dpi=DPI, bbox_inches='tight')
        if show_figure == True:
            plt.show()
        else:
            plt.close()
        return

    @classmethod
    def plot_residuals_histogram(cls, y_true, y_pred, savepath, show_figure=False, file_name='residual_histogram'):
        y_true = check_dimensions(y_true)
        y_pred = check_dimensions(y_pred)
        residuals = y_pred-y_true
        cls.plot_histogram(df=residuals,
                            savepath=savepath,
                            file_name=file_name,
                            x_label='Residuals',
                            show_figure=show_figure)
        return

    @classmethod
    def _get_histogram_bins(cls, df):

        bin_dividers = np.linspace(df.shape[0], 0.05*df.shape[0], df.shape[0])
        bin_list = list()
        try:
            for divider in bin_dividers:
                if divider == 0:
                    continue
                bins = int((df.shape[0])/divider)
                if bins < df.shape[0]/2:
                    bin_list.append(bins)
        except:
            num_bins = 10
        if len(bin_list) > 0:
            num_bins = max(bin_list)
        else:
            num_bins = 10
        return num_bins


### Helpers:

def make_plots(plots, y_true, y_pred, dataset_stdev, metrics, model, residuals, model_errors, has_model_errors,
               savepath, data_type, show_figure=False, recalibrate_errors=False, model_errors_cal=None):
    if 'Histogram' in plots:
        Histogram.plot_residuals_histogram(y_true=y_true,
                                           y_pred=y_pred,
                                           savepath=savepath,
                                           file_name='residual_histogram_'+str(data_type),
                                           show_figure=show_figure)
    if 'Scatter' in plots:
        Scatter.plot_predicted_vs_true(y_true=y_true,
                                       y_pred=y_pred,
                                       savepath=savepath,
                                       file_name='parity_plot_'+str(data_type),
                                       x_label='values',
                                       data_type=data_type,
                                       metrics_list=metrics,
                                       show_figure=show_figure)
    if 'Error' in plots:
        Error.plot_normalized_error(residuals=residuals,
                                    savepath=savepath,
                                    data_type=data_type,
                                    model_errors=model_errors,
                                    show_figure=show_figure)
        Error.plot_cumulative_normalized_error(residuals=residuals,
                                               savepath=savepath,
                                               data_type=data_type,
                                               model_errors=model_errors,
                                               show_figure=show_figure)
        if has_model_errors is True:
            Error.plot_rstat(savepath=savepath,
                             data_type=data_type,
                             model_errors=model_errors,
                             residuals=residuals,
                             show_figure=show_figure,
                             is_calibrated=False)
            Error.plot_real_vs_predicted_error(savepath=savepath,
                                               model=model,
                                               data_type=data_type,
                                               model_errors=model_errors,
                                               residuals=residuals,
                                               dataset_stdev=dataset_stdev,
                                               show_figure=show_figure,
                                               is_calibrated=False)
            if recalibrate_errors is True:
                Error.plot_rstat(savepath=savepath,
                                 data_type=data_type,
                                 residuals=residuals,
                                 model_errors=model_errors_cal,
                                 show_figure=show_figure,
                                 is_calibrated=True)
                Error.plot_rstat_uncal_cal_overlay(savepath=savepath,
                                                    data_type=data_type,
                                                    residuals=residuals,
                                                    model_errors=model_errors,
                                                   model_errors_cal=model_errors_cal,
                                                    show_figure=False)
                Error.plot_real_vs_predicted_error(savepath=savepath,
                                                    model=model,
                                                    data_type=data_type,
                                                   residuals=residuals,
                                                    model_errors=model_errors_cal,
                                                    dataset_stdev=dataset_stdev,
                                                    show_figure=show_figure,
                                                    is_calibrated=True)
                Error.plot_real_vs_predicted_error_uncal_cal_overlay(savepath=savepath,
                                                                    model=model,
                                                                    data_type=data_type,
                                                                    model_errors=model_errors,
                                                                     model_errors_cal=model_errors_cal,
                                                                    residuals=residuals,
                                                                    dataset_stdev=dataset_stdev,
                                                                    show_figure=False)
    return

def check_dimensions(y):
    """
    Method to check the dimensions of supplied data. Plotters need data to be 1D and often data is passed in as 2D

    Args:

        y: (numpy array or pd.DataFrame), array or dataframe of data used for plotting

    Returns:

        y: (pd.Series), series that is now 1D

    """
    if len(y.shape) > 1:
        if type(y) == pd.core.frame.DataFrame:
            y = pd.DataFrame.squeeze(y)
        elif type(y) == np.ndarray:
            y = pd.DataFrame(y.ravel()).squeeze()
            #y = y.ravel()
    else:
        if type(y) == np.ndarray:
            y = pd.DataFrame(y).squeeze()
    return y

def reset_index(y):
    return pd.DataFrame(np.array(y))

def trim_array(arr_list):
    """
    Method used to trim a set of arrays to make all arrays the same shape

    Args:

        arr_list: (list), list of numpy arrays, where arrays are different sizes

    Returns:

        arr_list: (), list of trimmed numpy arrays, where arrays are same size

    """

    # TODO: a better way to handle arrays with very different shapes? Otherwise average only uses # of points of smallest array
    # Need to make arrays all same shapes if they aren't
    sizes = [arr.shape[0] for arr in arr_list]
    size_min = min(sizes)
    arr_list_ = list()
    for i, arr in enumerate(arr_list):
        if arr.shape[0] > size_min:
            while arr.shape[0] > size_min:
                arr = np.delete(arr, -1)
        arr_list_.append(arr)
    arr_list = arr_list_
    return arr_list

def rounder(delta):
    """
    Method to obtain number of decimal places to report on plots

    Args:

        delta: (float), a float representing the change in two y values on a plot, used to obtain the plot axis spacing size

    Return:

        (int), an integer denoting the number of decimal places to use

    """
    if 0.001 <= delta < 0.01:
        return 3
    elif 0.01 <= delta < 0.1:
        return 2
    elif 0.1 <= delta < 1:
        return 1
    elif 1 <= delta < 100000:
        return 0
    else:
        return 0

def stat_to_string(name, value, nice_names):
    """
    Method that converts a metric object into a string for displaying on a plot

    Args:

        name: (str), long name of a stat metric or quantity

        value: (float), value of the metric or quantity

    Return:

        (str), a string of the metric name, adjusted to look nicer for inclusion on a plot

    """

    " Stringifies the name value pair for display within a plot "
    if name in nice_names:
        name = nice_names[name]
    else:
        name = name.replace('_', ' ')

    # has a name only
    if not value:
        return name
    # has a mean and std
    if isinstance(value, tuple):
        mean, std = value
        return f'{name}:' + '\n\t' + f'{mean:.3f}' + r'$\pm$' + f'{std:.3f}'
    # has a name and value only
    if isinstance(value, int) or (isinstance(value, float) and value%1 == 0):
        return f'{name}: {int(value)}'
    if isinstance(value, float):
        return f'{name}: {value:.3f}'
    return f'{name}: {value}' # probably a string

def plot_stats(fig, stats, x_align=0.65, y_align=0.90, font_dict=dict(), fontsize=14):
    """
    Method that prints stats onto the plot. Goes off screen if they are too long or too many in number.

    Args:

        fig: (matplotlib figure object), a matplotlib figure object

        stats: (dict), dict of statistics to be included with a plot

        x_align: (float), float denoting x position of where to align display of stats on a plot

        y_align: (float), float denoting y position of where to align display of stats on a plot

        font_dict: (dict), dict of matplotlib font options to alter display of stats on plot

        fontsize: (int), the fontsize of stats to display on plot

    Returns:

        None

    """

    stat_str = '\n'.join(stat_to_string(name, value, nice_names=nice_names())
                           for name,value in stats.items())

    fig.text(x_align, y_align, stat_str,
             verticalalignment='top', wrap=True, fontdict=font_dict, fontproperties=FontProperties(size=fontsize))

def make_fig_ax(aspect_ratio=0.5, x_align=0.65, left=0.10):
    """
    Method to make matplotlib figure and axes objects. Using Object Oriented interface from https://matplotlib.org/gallery/api/agg_oo_sgskip.html

    Args:

        aspect_ratio: (float), aspect ratio for figure and axes creation

        x_align: (float), x position to draw edge of figure. Needed so can display stats alongside plot

        left: (float), the leftmost position to draw edge of figure

    Returns:

        fig: (matplotlib fig object), a matplotlib figure object with the specified aspect ratio

        ax: (matplotlib ax object), a matplotlib axes object with the specified aspect ratio

    """
    # Set image aspect ratio:
    w, h = figaspect(aspect_ratio)
    fig = plt.figure(figsize=(w,h))
    #fig = Figure(figsize=(w, h))
    FigureCanvas(fig)

    # Set custom positioning, see this guide for more details:
    # https://python4astronomers.github.io/plotting/advanced.html
    #left   = 0.10
    bottom = 0.15
    right  = 0.01
    top    = 0.05
    width = x_align - left - right
    height = 1 - bottom - top
    ax = fig.add_axes((left, bottom, width, height), frameon=True)
    fig.set_tight_layout(False)
    
    return fig, ax

def make_fig_ax_square(aspect='equal', aspect_ratio=1):
    """
    Method to make square shaped matplotlib figure and axes objects. Using Object Oriented interface from

    https://matplotlib.org/gallery/api/agg_oo_sgskip.html

    Args:

        aspect: (str), 'equal' denotes x and y aspect will be equal (i.e. square)

        aspect_ratio: (float), aspect ratio for figure and axes creation

    Returns:

        fig: (matplotlib fig object), a matplotlib figure object with the specified aspect ratio

        ax: (matplotlib ax object), a matplotlib axes object with the specified aspect ratio

    """
    # Set image aspect ratio:
    w, h = figaspect(aspect_ratio)
    fig = Figure(figsize=(w,h))
    FigureCanvas(fig)
    ax = fig.add_subplot(111, aspect=aspect)

    return fig, ax

def make_axis_same(ax, max1, min1):
    """
    Method to make the x and y ticks for each axis the same. Useful for parity plots

    Args:

        ax: (matplotlib axis object), a matplotlib axes object

        max1: (float), the maximum value of a particular axis

        min1: (float), the minimum value of a particular axis

    Returns:

        None

    """
    if max1 - min1 > 5:
        step = (int(max1) - int(min1)) // 3
        ticks = range(int(min1), int(max1)+step, step)
    else:
        ticks = np.linspace(min1, max1, 5)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)

def nice_mean(ls):
    """
    Method to return mean of a list or equivalent array with NaN values

    Args:

        ls: (list), list of values

    Returns:

        (numpy array), array containing mean of list of values or NaN if list has no values

    """

    if len(ls) > 0:
        return np.mean(ls)
    return np.nan

def nice_std(ls):
    """
    Method to return standard deviation of a list or equivalent array with NaN values

    Args:

        ls: (list), list of values

    Returns:

        (numpy array), array containing standard deviation of list of values or NaN if list has no values

    """
    if len(ls) > 0:
        return np.std(ls)
    return np.nan

def round_down(num, divisor):
    """
    Method to return a rounded down number

    Args:

        num: (float), a number to round down

        divisor: (int), divisor to denote how to round down

    Returns:

        (float), the rounded-down number

    """

    return num - (num%divisor)

def round_up(num, divisor):
    """
    Method to return a rounded up number

    Args:

        num: (float), a number to round up

        divisor: (int), divisor to denote how to round up

    Returns:

        (float), the rounded-up number

    """
    return float(math.ceil(num / divisor)) * divisor

def get_divisor(high, low):
    """
    Method to obtain a sensible divisor based on range of two values

    Args:

        high: (float), a max data value

        low: (float), a min data value

    Returns:

        divisor: (float), a number used to make sensible axis ticks

    """

    delta = high-low
    divisor = 10
    if delta > 1000:
        divisor = 100
    if delta < 1000:
        if delta > 100:
            divisor = 10
        if delta < 100:
            if delta > 10:
                divisor = 1
            if delta < 10:
                if delta > 1:
                    divisor = 0.1
                if delta < 1:
                    if delta > 0.01:
                        divisor = 0.001
                else:
                    divisor = 0.001
    return divisor

def recursive_max(arr):
    """
    Method to recursively find the max value of an array of iterables.

    Credit: https://www.linkedin.com/pulse/ask-recursion-during-coding-interviews-identify-good-talent-veteanu/

    Args:

        arr: (numpy array), an array of values or iterables

    Returns:

        (float), max value in arr

    """
    return max(
        recursive_max(e) if isinstance(e, Iterable) else e
        for e in arr
    )

def recursive_min(arr):
    """
    Method to recursively find the min value of an array of iterables.

    Credit: https://www.linkedin.com/pulse/ask-recursion-during-coding-interviews-identify-good-talent-veteanu/

    Args:

        arr: (numpy array), an array of values or iterables

    Returns:

        (float), min value in arr

    """

    return min(
        recursive_min(e) if isinstance(e, Iterable) else e
        for e in arr
    )

def recursive_max_and_min(arr):
    """
    Method to recursively return max and min of values or iterables in array

    Args:

        arr: (numpy array), an array of values or iterables

    Returns:

        (tuple), tuple containing max and min of arr

    """
    return recursive_max(arr), recursive_min(arr)

def _set_tick_labels(ax, maxx, minn):
    """
    Method that sets the x and y ticks to be in the same range

    Args:

        ax: (matplotlib axes object), a matplotlib axes object

        maxx: (float), a maximum value

        minn: (float), a minimum value

    Returns:

        None

    """
    _set_tick_labels_different(ax, maxx, minn, maxx, minn) # I love it when this happens

def _set_tick_labels_different(ax, max_tick_x, min_tick_x, max_tick_y, min_tick_y):
    """
    Method that sets the x and y ticks, when the axes have different ranges

    Args:

        ax: (matplotlib axes object), a matplotlib axes object

        max_tick_x: (float), the maximum tick value for the x axis

        min_tick_x: (float), the minimum tick value for the x axis

        max_tick_y: (float), the maximum tick value for the y axis

        min_tick_y: (float), the minimum tick value for the y axis

    Returns:

        None

    """

    tickvals_x = nice_range(min_tick_x, max_tick_x)
    tickvals_y = nice_range(min_tick_y, max_tick_y)

    if tickvals_x[-1]-tickvals_x[len(tickvals_x)-2] < tickvals_x[len(tickvals_x)-3]-tickvals_x[len(tickvals_x)-4]:
        tickvals_x = tickvals_x[:-1]
    if tickvals_y[-1]-tickvals_y[len(tickvals_y)-2] < tickvals_y[len(tickvals_y)-3]-tickvals_y[len(tickvals_y)-4]:
        tickvals_y = tickvals_y[:-1]
    #tickvals_x = _clean_tick_labels(tickvals=tickvals_x, delta=max_tick_x-min_tick_x)
    #tickvals_y = _clean_tick_labels(tickvals=tickvals_y, delta=max_tick_y - min_tick_y)

    ax.set_xticks(ticks=tickvals_x)
    ax.set_yticks(ticks=tickvals_y)

    ticklabels_x = [str(tick) for tick in tickvals_x]
    ticklabels_y = [str(tick) for tick in tickvals_y]

    rotation = 0
    # Look at length of x tick labels to see if may be possibly crowded. If so, rotate labels
    tick_length = len(str(tickvals_x[1]))
    if tick_length >= 4:
        rotation = 45
    ax.set_xticklabels(labels=ticklabels_x, fontsize=14, rotation=rotation)
    ax.set_yticklabels(labels=ticklabels_y, fontsize=14)

def _clean_tick_labels(tickvals, delta):
    """
    Method to attempt to clean up axis tick values so they don't overlap from being too dense

    Args:

        tickvals: (list), a list containing the initial axis tick values

        delta: (float), number representing the numerical difference of two ticks

    Returns:

        tickvals_clean: (list), a list containing the updated axis tick values

    """
    tickvals_clean = list()
    if delta >= 100:
        for i, val in enumerate(tickvals):
            if i <= len(tickvals)-1:
                if tickvals[i]-tickvals[i-1] >= 100:
                    tickvals_clean.append(val)
    else:
        tickvals_clean = tickvals
    return tickvals_clean

## Math utilities to aid plot_helper to make ranges

def nice_range(lower, upper):
    """
    Method to create a range of values, including the specified start and end points, with nicely spaced intervals

    Args:

        lower: (float or int), lower bound of range to create

        upper: (float or int), upper bound of range to create

    Returns:

        (list), list of numerical values in established range

    """

    flipped = 1 # set to -1 for inverted

    # Case for validation where nan is passed in
    if np.isnan(lower):
        lower = 0
    if np.isnan(upper):
        upper = 0.1

    if upper < lower:
        upper, lower = lower, upper
        flipped = -1
    return [_int_if_int(x) for x in _nice_range_helper(lower, upper)][::flipped]

def _nice_range_helper(lower, upper):
    """
    Method to help make a better range of axis ticks

    Args:

        lower: (float), lower value of axis ticks

        upper: (float), upper value of axis ticks

    Returns:

        upper: (float), modified upper tick value fixed based on set of axis ticks

    """
    steps = 8
    diff = abs(lower - upper)

    # special case where lower and upper are the same
    if diff == 0:
        return [lower,]

    # the exact step needed
    step = diff / steps

    # a rough estimate of best step
    step = _nearest_pow_ten(step) # whole decimal increments

    # tune in one the best step size
    factors = [0.1, 0.2, 0.5, 1, 2, 5, 10]

    # use this to minimize how far we are from ideal step size
    def best_one(steps_factor):
        steps_count, factor = steps_factor
        return abs(steps_count - steps)
    n_steps, best_factor = min([(diff / (step * f), f) for f in factors], key = best_one)

    #print('should see n steps', ceil(n_steps + 2))
    # multiply in the optimal factor for getting as close to ten steps as we can
    step = step * best_factor

    # make the bounds look nice
    lower = _three_sigfigs(lower)
    upper = _three_sigfigs(upper)

    start = _round_up(lower, step)

    # prepare for iteration
    x = start # pointless init
    i = 0

    # itereate until we reach upper
    while x < upper - step:
        x = start + i * step
        yield _three_sigfigs(x) # using sigfigs because of floating point error
        i += 1

    # finish off with ending bound
    yield upper

def _three_sigfigs(x):
    """
    Method invoking special case of _n_sigfigs to return 3 sig figs

    Args:

        x: (float), an axis tick number

    Returns:

        (float), number of sig figs (always 3)

    """
    return _n_sigfigs(x, 3)

def _n_sigfigs(x, n):
    """
    Method to return number of sig figs to use for axis ticks

    Args:

        x: (float), an axis tick number

    Returns:

        (float), number of sig figs

    """
    sign = 1
    if x == 0:
        return 0
    if x < 0: # case for negatives
        x = -x
        sign = -1
    if x < 1:
        base = n - round(log(x, 10))
    else:
        base = (n-1) - round(log(x, 10))
    return sign * round(x, base)

def _nearest_pow_ten(x):
    """
    Method to return the nearest power of ten for an axis tick value

    Args:

        x: (float), an axis tick number

    Returns:

        (float), nearest power of ten of x

    """
    sign = 1
    if x == 0:
        return 0
    if x < 0: # case for negatives
        x = -x
        sign = -1
    return sign*10**ceil(log(x, 10))

def _int_if_int(x):
    """
    Method to return integer mapped value of x

    Args:

        x: (float or int), a number

    Returns:

        x: (float), value of x mapped as integer

    """
    if int(x) == x:
        return int(x)
    return x

def _round_up(x, inc):
    """
    Method to round up the value of x

    Args:

        x: (float or int), a number

        inc: (float), an increment for axis ticks

    Returns:

        (float), value of x rounded up

    """
    sign = 1
    if x < 0: # case for negative
        x = -x
        sign = -1

    return sign * inc * ceil(x / inc)

def nice_names():
    nice_names = {
    # classification:
    'accuracy': 'Accuracy',
    'f1_binary': '$F_1$',
    'f1_macro': 'f1_macro',
    'f1_micro': 'f1_micro',
    'f1_samples': 'f1_samples',
    'f1_weighted': 'f1_weighted',
    'log_loss': 'log_loss',
    'precision_binary': 'Precision',
    'precision_macro': 'prec_macro',
    'precision_micro': 'prec_micro',
    'precision_samples': 'prec_samples',
    'precision_weighted': 'prec_weighted',
    'recall_binary': 'Recall',
    'recall_macro': 'rcl_macro',
    'recall_micro': 'rcl_micro',
    'recall_samples': 'rcl_samples',
    'recall_weighted': 'rcl_weighted',
    'roc_auc': 'ROC_AUC',
    # regression:
    'explained_variance': 'expl_var',
    'mean_absolute_error': 'MAE',
    'mean_squared_error': 'MSE',
    'mean_squared_log_error': 'MSLE',
    'median_absolute_error': 'MedAE',
    'root_mean_squared_error': 'RMSE',
    'rmse_over_stdev': r'RMSE/$\sigma_y$',
    'r2_score': '$R^2$',
    'r2_score_noint': '$R^2_{noint}$',
    'r2_score_adjusted': '$R^2_{adjusted}$',
    'r2_score_fitted': '$R^2_{fitted}$'
    }
    return nice_names
