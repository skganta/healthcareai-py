"""
Trains Supervised Models.

Provides users a simple interface for machine learning.

More advanced users may use `AdvancedSupervisedModelTrainer`
"""

from contextlib import contextmanager

import healthcareai.pipelines.data_preparation as hcai_pipelines
import healthcareai.trained_models.trained_supervised_model as hcai_tsm
import healthcareai.common.cardinality_checks as hcai_ordinality
from healthcareai.advanced_supvervised_model_trainer import \
    AdvancedSupervisedModelTrainer
from healthcareai.common.categorical_levels import calculate_categorical_frequencies


class SupervisedModelTrainer(object):
    """Train supervised models.

    This class trains models using several common classifiers and regressors and
    reports appropriate metrics.
    """

    def __init__(
            self,
            dataframe,
            predicted_column,
            model_type,
            impute=True,
            grain_column=None,
            binary_positive_label=None,
            verbose=False):
        """
        Set up a SupervisedModelTrainer.

        Helps the user by checking for high cardinality features (such as IDs or
        other unique identifiers) and low cardinality features (a column where
        all values are equal.

        If you have a binary classification task (one with two categories of
        predictions), there are many common ways to encode your prediction
        categories. healthcareai helps you by making these assumptions about
        which is the positive class label. healthcareai assumes the following
        are 'positive labels':

        | Labels | Positive Label |
        | ------ | -------------- |
        | `True` | `True`/`False` |
        | `1`    | `1`/`0`        |
        | `1`    | `1`/`-1`       |
        | `Y`    | `Y`/`N`        |
        | `Yes`  | `Yes`/`No`     |

        If you have another encoding you prefer to use you may specify the
        `binary_positive_label` argument. For example, if you want to
        identify `high_utilizers` vs `low_utilizers`) you would add the
        `binary_positive_label='high_utilizers` argument when creating your
        `SupervisedModelTrainer`.

        Args:
            dataframe (pandas.core.frame.DataFrame): The training data in a pandas dataframe
            predicted_column (str): The name of the prediction column
            model_type (str): the trainer type ('classification' or 'regression')
            impute (bool): True to impute data (mean of numeric columns and mode of categorical ones). False to drop rows that contain any null values.
            grain_column (str): The name of the grain column
            binary_positive_label (str|int): Optional positive class label for binary classification tasks.
            verbose (bool): Set to true for verbose output. Defaults to False.
        """
        self.predicted_column = predicted_column
        self.grain_column = grain_column
        self.binary_positive_label = binary_positive_label

        # Build the pipeline
        # Note: Missing numeric values are imputed in prediction. If we don't
        # impute, then some rows on the prediction
        # data frame will be removed, which results in missing predictions.
        pipeline = hcai_pipelines.full_pipeline(model_type, predicted_column,
                                                grain_column, impute=impute)
        prediction_pipeline = hcai_pipelines.full_pipeline(model_type,
                                                           predicted_column,
                                                           grain_column,
                                                           impute=True)

        # Run a low and high cardinality check. Warn the user, and allow
        # them to proceed.
        hcai_ordinality.check_high_cardinality(dataframe, self.grain_column)
        hcai_ordinality.check_one_cardinality(dataframe)

        # Run the raw data through the data preparation pipeline
        clean_dataframe = pipeline.fit_transform(dataframe)
        _ = prediction_pipeline.fit_transform(dataframe)

        # Instantiate the advanced class
        self._advanced_trainer = AdvancedSupervisedModelTrainer(
            dataframe=clean_dataframe,
            model_type=model_type,
            predicted_column=predicted_column,
            grain_column=grain_column,
            original_column_names=dataframe.columns.values,
            binary_positive_label=self.binary_positive_label,
            verbose=verbose)

        # Save the pipeline to the parent class
        self._advanced_trainer.pipeline = prediction_pipeline

        # Split the data into train and test
        self._advanced_trainer.train_test_split()

        self._advanced_trainer.categorical_column_info = calculate_categorical_frequencies(
            dataframe=dataframe,
            columns_to_ignore=[grain_column, predicted_column])

    @property
    def clean_dataframe(self):
        """Return the dataframe after the preparation pipeline."""
        return self._advanced_trainer.dataframe

    @property
    def class_labels(self):
        """Return class labels."""
        return self._advanced_trainer.class_labels

    @property
    def number_of_classes(self):
        """Return number of classes."""
        return self._advanced_trainer.number_of_classes

    def random_forest(self, feature_importance_limit=15, save_plot=False):
        """
        Train a random forest model and print model performance metrics.

        Args:
            feature_importance_limit (int): The maximum number of features to
            show in the feature importance plot
            save_plot (bool): For the feature importance plot, True to save
            plot (will not display). False by default to
                display.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        if self._advanced_trainer.model_type is 'classification':
            return self.random_forest_classification(
                feature_importance_limit=feature_importance_limit,
                save_plot=save_plot)
        elif self._advanced_trainer.model_type is 'regression':
            return self.random_forest_regression()

    def knn(self):
        """Train a knn model and print model performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('KNN') as model:
            model.trained_model = self._advanced_trainer.knn(
                scoring_metric='accuracy',
                hyperparameter_grid=None,
                randomized_search=True)

            return model.trained_model

    def random_forest_regression(self):
        """Train a random forest regression model and print performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('Random Forest Regression') as model:
            model.trained_model = self._advanced_trainer.random_forest_regressor(
                trees=200,
                scoring_metric='neg_mean_squared_error',
                randomized_search=True)

            return model.trained_model

    def random_forest_classification(self, feature_importance_limit=15,
                                     save_plot=False):
        """Train a random forest classification model, print metrics and show a feature importance plot.

        Args:
            feature_importance_limit (int): The maximum number of features to show in the feature importance plot
            save_plot (bool): For the feature importance plot, True to save plot (will not display). False by default to
                display.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('Random Forest Classification') as model:
            model.trained_model = self._advanced_trainer.random_forest_classifier(
                trees=200,
                scoring_metric='accuracy',
                randomized_search=True)

            # Save or show the feature importance graph
            hcai_tsm.plot_rf_features_from_tsm(
                model.trained_model,
                self._advanced_trainer.x_train,
                feature_limit=feature_importance_limit,
                save=save_plot)

            return model.trained_model

    def logistic_regression(self):
        """Train a logistic regression model and print performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('Logistic Regression') as model:
            model.trained_model = self._advanced_trainer.logistic_regression(
                randomized_search=False)
            return model.trained_model

    def linear_regression(self):
        """Train a linear regression model and print performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('Linear Regression') as model:
            model.trained_model = self._advanced_trainer.linear_regression(
                randomized_search=False)
            return model.trained_model

    def lasso_regression(self):
        """Train a lasso regression model and print performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        with self.nice_training_output('Lasso Regression') as model:
            model.trained_model = self._advanced_trainer.lasso_regression(
                randomized_search=False)
            return model.trained_model

    def ensemble(self):
        """Train a ensemble model and print performance metrics.

        Returns:
            TrainedSupervisedModel: A trained supervised model.
        """
        # TODO consider making a scoring parameter-which will require more logic
        with self.nice_training_output('ensemble {}'.format(
                self._advanced_trainer.model_type)) as model:
            # Train the appropriate ensemble of models
            if self._advanced_trainer.model_type is 'classification':
                metric = 'accuracy'
                model.trained_model = self._advanced_trainer.ensemble_classification(
                    scoring_metric=metric)
            elif self._advanced_trainer.model_type is 'regression':
                # TODO stub
                metric = 'neg_mean_squared_error'
                model.trained_model = self._advanced_trainer.ensemble_regression(
                    scoring_metric=metric)

            print(
                'Based on the scoring metric {}, the best algorithm found is: {}'.format(
                    metric,
                    model.trained_model.algorithm_name))

            return model.trained_model

    @property
    def advanced_features(self):
        """
        Return the underlying AdvancedSupervisedModelTrainer instance.

        For advanced users only.
        """
        return self._advanced_trainer

    @contextmanager
    def nice_training_output(self, model_name):
        """
        Wrap model training with nice console output before and after training.

        This allows all algorithms to have consistent console output while
        having custom training (or other) code.

        Args:
            model_name (str): The name of the model used for pretty printing.
        """
        # Instantiate a temporary Model object to facilitate the unique code in
        # the context manager
        temp_model = ContextManagerModel(model_name)

        if self._advanced_trainer.is_classification:
            print('\nTraining {} model on {} classes: {}\n'.format(
                model_name,
                self.number_of_classes,
                self.class_labels))
        else:
            print('\nTraining {}\n'.format(temp_model.model_name))

        # Give the model back to the context to allow for unique training code
        yield temp_model

        # Display the trained model metrics
        temp_model.trained_model.print_training_results()


class ContextManagerModel(object):
    """A tiny class used by the `model_training` context manager."""

    def __init__(self, model_name, trained_model=None):
        """Create a new instance."""
        self.model_name = model_name
        self.trained_model = trained_model
