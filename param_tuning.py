from abc import abstractmethod
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, cross_val_score, KFold
from sklearn.metrics import r2_score
from bayes_opt import BayesianOptimization
import time
import numbers
import copy
import pandas as pd
import matplotlib.pyplot as plt

class ParamTuning():
    """
    パラメータチューニング用基底クラス
    """

    # 共通定数
    SEED = 42  # デフォルト乱数シード
    SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]  # デフォルト複数乱数シード
    CV_NUM = 5  # 最適化時のクロスバリデーションのデフォルト分割数
    
    # 学習器のインスタンス
    CV_MODEL = None
    # 学習時のパラメータのデフォルト値
    FIT_PARAMS = {}
     # 最適化で最大化するデフォルト評価指標('r2', 'neg_mean_squared_error', 'neg_mean_squared_log_error')
    SCORING = None

    # 最適化対象外パラメータ
    NOT_OPT_PARAMS = {}

    # グリッドサーチ用パラメータ
    CV_PARAMS_GRID = {}
    CV_PARAMS_GRID.update(NOT_OPT_PARAMS)

    # ランダムサーチ用パラメータ
    N_ITER_RANDOM = 200  # ランダムサーチの繰り返し回数
    CV_PARAMS_RANDOM = {}
    CV_PARAMS_RANDOM.update(NOT_OPT_PARAMS)

    # ベイズ最適化用パラメータ
    N_ITER_BAYES = 100  # ベイズ最適化の繰り返し回数
    INIT_POINTS = 20  # 初期観測点の個数(ランダムな探索を何回行うか)
    ACQ = 'ei'  # 獲得関数(https://ohke.hateblo.jp/entry/2018/08/04/230000)
    BAYES_PARAMS = {}
    BAYES_NOT_OPT_PARAMS = {k: v[0] for k, v in NOT_OPT_PARAMS.items()}

    # 検証曲線用パラメータ範囲
    VALIDATION_CURVE_PARAMS = {}

    def __init__(self, X, y, X_colnames, y_colname=None):
        """
        初期化

        Parameters
        ----------
        X : ndarray
            説明変数データ(pandasではなくndarray)
        y : ndarray
            目的変数データ
        X_colnames : list(str)
            説明変数のフィールド名
        y_colname : str
            目的変数のフィールド名
        """
        if X.shape[1] != len(X_colnames):
            raise Exception('width of X must be equal to length of X_colnames')
        self.X = X
        self.y = y
        self.X_colnames = X_colnames
        self.y_colname = y_colname
        self.tuning_params = None
        self.bayes_not_opt_params = None
        self.seed = None
        self.cv = None
        self.fit_params = None
        self.best_estimator_ = None
    
    def _train_param_generation(self, src_fit_params):
        """
        学習データから学習時パラメータの生成（例: XGBoostのeval_list）
        通常はデフォルトのままだが、必要であれば継承先でオーバーライド

        Parameters
        ----------
        src_fit_params : Dict
            処理前の学習時パラメータ
        """
        return src_fit_params

    def grid_search_tuning(self, cv_model=None, cv_params=None, cv=None, seed=None, scoring=None, **fit_params):
        """
        グリッドサーチ＋クロスバリデーション

        Parameters
        ----------
        cv_model : Dict
            最適化対象の学習器インスタンス
        cv_params : Dict
            最適化対象のパラメータ一覧
        cv : int or KFold
            クロスバリデーション分割法(未指定時 or int入力時はkFoldで分割)
        seed : int
            乱数シード(クロスバリデーション分割用、xgboostの乱数シードはcv_paramsで指定するので注意)
        scoring : str
            最適化で最大化する評価指標('r2', 'neg_mean_squared_error', 'neg_mean_squared_log_error')
        fit_params : Dict
            学習時のパラメータをdict指定(例: XGBoostのearly_stopping_rounds)
        """
        # 処理時間測定
        start = time.time()

        # 引数非指定時、クラス変数から取得
        if cv_model == None:
            cv_model = copy.deepcopy(self.CV_MODEL)
        if cv_params == None:
            cv_params = self.CV_PARAMS_GRID
        if cv == None:
            cv = self.CV_NUM
        if seed == None:
            seed = self.SEED
        if scoring == None:
            scoring = self.SCORING
        if fit_params == {}:
            fit_params = self.FIT_PARAMS
        # 引数をプロパティに反映
        cv_params['random_state'] = [seed]
        self.tuning_params = cv_params
        self.seed = seed
        self.scoring = scoring
        # 学習データから生成されたパラメータの追加
        fit_params = self._train_param_generation(fit_params)
        self.fit_params = fit_params
        # 分割法未指定時、cv_numとseedに基づきランダムに分割
        if isinstance(cv, numbers.Integral):
            cv = KFold(n_splits=cv, shuffle=True, random_state=seed)
        self.cv = cv

        # グリッドサーチのインスタンス作成
        # n_jobs=-1にするとCPU100%で全コア並列計算。とても速い。
        gridcv = GridSearchCV(cv_model, cv_params, cv=cv,
                          scoring=scoring, n_jobs=-1)

        # グリッドサーチ実行（学習実行）
        gridcv.fit(self.X,
               self.y,
               **fit_params
               )
        elapsed_time = time.time() - start

        # 最適パラメータの表示
        print('最適パラメータ ' + str(gridcv.best_params_))

        # 最適モデルの保持
        self.best_estimator_ = gridcv.best_estimator_

        # グリッドサーチでの探索結果を返す
        return gridcv.best_params_, gridcv.best_score_, elapsed_time

    def random_search_tuning(self, cv_model=None, cv_params=None, cv=None, seed=None, scoring=None, n_iter=None, **fit_params):
        """
        ランダムサーチ＋クロスバリデーション

        Parameters
        ----------
        cv_model : Dict
            最適化対象の学習器インスタンス
        cv_params : dict
            最適化対象のパラメータ一覧
        cv : int or KFold
            クロスバリデーション分割法(未指定時 or int入力時はkFoldで分割)
        seed : int
            乱数シード(クロスバリデーション分割用、xgboostの乱数シードはcv_paramsで指定するので注意)
        scoring : str
            最適化で最大化する評価指標('r2', 'neg_mean_squared_error', 'neg_mean_squared_log_error')
        n_iter : int
            ランダムサーチの繰り返し回数
        fit_params : Dict
            学習時のパラメータをdict指定(例: XGBoostのearly_stopping_rounds)
        """
        # 処理時間測定
        start = time.time()

        # 引数非指定時、クラス変数から取得
        if cv_model == None:
            cv_model = copy.deepcopy(self.CV_MODEL)
        if cv_params == None:
            cv_params = self.CV_PARAMS_RANDOM
        if cv == None:
            cv = self.CV_NUM
        if seed == None:
            seed = self.SEED
        if scoring == None:
            scoring = self.SCORING
        if n_iter == None:
            n_iter = self.N_ITER_RANDOM
        if fit_params == {}:
            fit_params = self.FIT_PARAMS
        # 引数をプロパティに反映
        cv_params['random_state'] = [seed]
        self.tuning_params = cv_params
        self.seed = seed
        self.scoring = scoring
        # 学習データから生成されたパラメータの追加
        fit_params = self._train_param_generation(fit_params)
        self.fit_params = fit_params
        # 分割法未指定時、cv_numとseedに基づきランダムに分割
        if isinstance(cv, numbers.Integral):
            cv = KFold(n_splits=cv, shuffle=True, random_state=seed)
        self.cv = cv

        # ランダムサーチのインスタンス作成
        # n_jobs=-1にするとCPU100%で全コア並列計算。とても速い。
        randcv = RandomizedSearchCV(cv_model, cv_params, cv=cv,
                                random_state=seed, n_iter=n_iter, scoring=scoring, n_jobs=-1)

        # ランダムサーチ実行
        randcv.fit(self.X,
               self.y,
               **fit_params
               )
        elapsed_time = time.time() - start

        # 最適パラメータの表示
        print('最適パラメータ ' + str(randcv.best_params_))
        # 最適モデルの保持
        self.best_estimator_ = randcv.best_estimator_

        # ランダムサーチで探索した最適パラメータ、特徴量重要度、所要時間を返す
        return randcv.best_params_, randcv.best_score_, elapsed_time

    @abstractmethod
    def _bayes_evaluate(self):
        """
         ベイズ最適化時の評価指標算出メソッド (継承先でオーバーライドが必須)
        """
        pass

    def bayes_opt_tuning(self, cv_model=None, bayes_params=None, cv=None, seed=None, scoring=None, n_iter=None, init_points=None, acq=None, bayes_not_opt_params=None, **fit_params):
        """
        ベイズ最適化(bayes_opt)

        Parameters
        ----------
        beyes_params : dict
            最適化対象のパラメータ範囲
        cv : int or KFold
            クロスバリデーション分割法(未指定時 or int入力時はkFoldで分割)
        seed : int
            乱数シード(クロスバリデーション分割用、xgboostの乱数シードはcv_paramsで指定するので注意)
        scoring : str
            最適化で最大化する評価指標('r2', 'neg_mean_squared_error', 'neg_mean_squared_log_error')
        n_iter : int
            ベイズ最適化の繰り返し回数
        init_points : int
            初期観測点の個数(ランダムな探索を何回行うか)
        acq : str
            獲得関数('ei', 'pi', 'ucb')
        bayes_not_opt_params : dict
            最適化対象外のパラメータ一覧
        fit_params : Dict
            学習時のパラメータをdict指定(例: XGBoostのearly_stopping_rounds)
        """
        # 処理時間測定
        start = time.time()

        # 引数非指定時、クラス変数から取得
        if cv_model == None:
            cv_model = copy.deepcopy(self.CV_MODEL)
        if bayes_params == None:
            bayes_params = self.BAYES_PARAMS
        if cv == None:
            cv = self.CV_NUM
        if seed == None:
            seed = self.SEED
        if scoring == None:
            scoring = self.SCORING
        if n_iter == None:
            n_iter = self.N_ITER_BAYES
        if init_points == None:
            init_points = self.INIT_POINTS
        if acq == None:
            acq = self.ACQ
        if bayes_not_opt_params == None:
            bayes_not_opt_params = self.BAYES_NOT_OPT_PARAMS
        if fit_params == {}:
            fit_params = self.FIT_PARAMS
        # 引数をプロパティに反映
        self.tuning_params = bayes_params
        self.bayes_not_opt_params = bayes_not_opt_params
        self.seed = seed
        self.scoring = scoring
        # 学習データから生成されたパラメータの追加
        fit_params = self._train_param_generation(fit_params)
        self.fit_params = fit_params
        # 分割法未指定時、cv_numとseedに基づきランダムに分割
        if isinstance(cv, numbers.Integral):
            cv = KFold(n_splits=cv, shuffle=True, random_state=seed)
        self.cv = cv

        # ベイズ最適化を実行
        xgb_bo = BayesianOptimization(
            self._bayes_evaluate, bayes_params, random_state=seed)
        xgb_bo.maximize(init_points=init_points, n_iter=n_iter, acq=acq)
        elapsed_time = time.time() - start

        # 評価指標が最大となったときのパラメータを取得
        best_params = xgb_bo.max['params']
        best_params['min_child_weight'] = int(
            best_params['min_child_weight'])  # 小数で最適化されるのでint型に直す
        best_params['max_depth'] = int(
            best_params['max_depth'])  # 小数で最適化されるのでint型に直す
        # 最適化対象以外のパラメータも追加
        best_params.update(self.BAYES_NOT_OPT_PARAMS)
        best_params['random_state'] = self.seed
        # 評価指標の最大値を取得
        best_score = xgb_bo.max['target']

        # 最適モデル保持のため学習（特徴量重要度算出等）
        best_model = copy.deepcopy(cv_model)
        best_model.set_params(**best_params)
        best_model.fit(self.X,
                  self.y,
                  **fit_params
                  )
        self.best_estimator_ = best_model
        # ベイズ最適化で探索した最適パラメータ、評価指標最大値、所要時間を返す
        return best_params, best_score, elapsed_time


    def get_feature_importances(self, ax=None):
        """
        特徴量重要度の表示と取得

        Parameters
        ----------
        ax : 
            表示対象のax（Noneなら新規作成）
        """
        if self.best_estimator_ is not None:
            # 特徴量重要度の表示
            features = list(reversed(self.X_colnames))
            importances = list(
            reversed(self.best_estimator_.feature_importances_.tolist()))
            if ax == None:
                plt.barh(features, importances)
            else:
                ax.barh(features, importances)
            # 特徴量重要度の
            return self.best_estimator_.feature_importances_
        else:

            return None