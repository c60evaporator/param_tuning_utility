from param_tuning import ParamTuning
from sklearn.model_selection import cross_val_score
from sklearn.svm import SVC, SVR
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import copy

class SVMRegressorTuning(ParamTuning):
    """
    サポートベクター回帰チューニング用クラス
    """

    # 共通定数
    SEED = 42  # デフォルト乱数シード
    SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]  # デフォルト複数乱数シード
    CV_NUM = 5  # 最適化時のクロスバリデーションのデフォルト分割数
    
    # 学習器のインスタンス (標準化+SVRのパイプライン)
    CV_MODEL = Pipeline([("scaler", StandardScaler()), ("svr", SVR())])
    # 学習時のパラメータのデフォルト値
    FIT_PARAMS = {}
    # 最適化で最大化するデフォルト評価指標('r2', 'neg_mean_squared_error', 'neg_mean_squared_log_error')
    SCORING = 'neg_mean_squared_error'

    # 最適化対象外パラメータ
    NOT_OPT_PARAMS = {'kernel': ['rbf'],  # カーネルの種類 (基本は'rbf')
                      }

    # グリッドサーチ用パラメータ
    CV_PARAMS_GRID = {'gamma': [0.01, 0.03, 0.1, 0.3, 1, 3, 10],  # RBFカーネルのgamma (小さいと曲率小、大きいと曲率大)
                      'C': [0.1, 0.3, 1, 3, 10],  # 正則化項C (小さいと未学習寄り、大きいと過学習寄り)
                      'epsilon': [0, 0.1, 0.2, 0.3]  # εチューブの範囲 (大きいほど、誤差関数算出対象=サポートベクターから除外されるデータ点が多くなる)
                      }
    CV_PARAMS_GRID.update(NOT_OPT_PARAMS)  # 最適化対象外パラメータを追加

    # ランダムサーチ用パラメータ
    N_ITER_RANDOM = 200  # ランダムサーチの繰り返し回数
    CV_PARAMS_RANDOM = {'gamma': [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10],
                      'C': [0.1, 0.2, 0.5, 1, 2, 5, 10],
                      'epsilon': [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
                        }
    CV_PARAMS_RANDOM.update(NOT_OPT_PARAMS)  # 最適化対象外パラメータを追加

    # ベイズ最適化用パラメータ
    N_ITER_BAYES = 100  # ベイズ最適化の繰り返し回数
    INIT_POINTS = 20  # 初期観測点の個数(ランダムな探索を何回行うか)
    ACQ = 'ei'  # 獲得関数(https://ohke.hateblo.jp/entry/2018/08/04/230000)
    BAYES_PARAMS = {'gamma': (0.01, 10),
                    'C': (0.1, 10),
                    'epsilon': (0, 0.3)
                    }
    INT_PARAMS = []
    BAYES_NOT_OPT_PARAMS = {k: v[0] for k, v in NOT_OPT_PARAMS.items()}  # ベイズ最適化対象外パラメータ

    # 範囲選択検証曲線用パラメータ範囲
    VALIDATION_CURVE_PARAMS = {'gamma': [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100],
                      'C': [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100],
                      'epsilon': [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
                    }
    # 検証曲線表示時のスケール('linear', 'log')
    VALIDATION_CURVE_SCALES = {'gamma': 'log',
                      'C': 'log',
                      'epsilon': 'linear'
                      }

    def _train_param_generation(self, src_fit_params):
        """
        入力データから学習時パラメータの生成 (eval_set)
        
        Parameters
        ----------
        src_fit_params : Dict
            処理前の学習時パラメータ
        """
        return src_fit_params

    def _bayes_evaluate(self, gamma, C, epsilon):
        """
         ベイズ最適化時の評価指標算出メソッド
        """
        # 最適化対象のパラメータ
        params = {'gamma': gamma,
                  'C': C,
                  'epsilon': epsilon
                  }
        params = self._int_conversion(params, self.int_params)  # 整数パラメータはint型に変換
        params.update(self.bayes_not_opt_params)  # 最適化対象以外のパラメータも追加
        # パイプライン処理のとき、パラメータに学習器名を追加
        params = self._add_learner_name(self.cv_model, params)
        # XGBoostのモデル作成
        cv_model = copy.deepcopy(self.cv_model)
        cv_model.set_params(**params)

        # cross_val_scoreでクロスバリデーション
        scores = cross_val_score(cv_model, self.X, self.y, cv=self.cv,
                                 scoring=self.scoring, fit_params=self.fit_params, n_jobs=-1)
        val = scores.mean()

        # スクラッチでクロスバリデーション
        # scores = []
        # for train, test in self.cv.split(self.X, self.y):
        #     X_train = self.X[train]
        #     y_train = self.y[train]
        #     X_test = self.X[test]
        #     y_test = self.y[test]
        #     cv_model.fit(X_train,
        #              y_train,
        #              eval_set=[(X_train, y_train)],
        #              early_stopping_rounds=self.early_stopping_rounds,
        #              verbose=0
        #              )
        #     pred = cv_model.predict(X_test)
        #     score = r2_score(y_test, pred)
        #     scores.append(score)
        # val = sum(scores)/len(scores)

        return val


class SVMClassifierTuning(ParamTuning):
    """
    サポートベクター回帰チューニング用クラス
    """

    # 共通定数
    SEED = 42  # デフォルト乱数シード
    SEEDS = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]  # デフォルト複数乱数シード
    CV_NUM = 5  # 最適化時のクロスバリデーションのデフォルト分割数
    
    # 学習器のインスタンス (標準化+SVRのパイプライン)
    CV_MODEL = Pipeline([("scaler", StandardScaler()), ("svc", SVC())])
    # 学習時のパラメータのデフォルト値
    FIT_PARAMS = {}
    # 最適化で最大化するデフォルト評価指標('neg_log_loss', 'roc_auc', 'PR-AUC', 'F1-score', 'F1_macro')
    SCORING = 'neg_log_loss'

    # 最適化対象外パラメータ
    NOT_OPT_PARAMS = {'kernel': ['rbf'],  # カーネルの種類 (基本は'rbf')
                      }

    # グリッドサーチ用パラメータ
    CV_PARAMS_GRID = {'gamma': [0.01, 0.03, 0.1, 0.3, 1, 3, 10],  # RBFカーネルのgamma (小さいと曲率小、大きいと曲率大)
                      'C': [0.1, 0.3, 1, 3, 10]  # 正則化項C (小さいと未学習寄り、大きいと過学習寄り)
                      }
    CV_PARAMS_GRID.update(NOT_OPT_PARAMS)

    # ランダムサーチ用パラメータ
    N_ITER_RANDOM = 200  # ランダムサーチの繰り返し回数
    CV_PARAMS_RANDOM = {'gamma': [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10],
                      'C': [0.1, 0.2, 0.5, 1, 2, 5, 10]
                        }
    CV_PARAMS_RANDOM.update(NOT_OPT_PARAMS)

    # ベイズ最適化用パラメータ
    N_ITER_BAYES = 100  # ベイズ最適化の繰り返し回数
    INIT_POINTS = 20  # 初期観測点の個数(ランダムな探索を何回行うか)
    ACQ = 'ei'  # 獲得関数(https://ohke.hateblo.jp/entry/2018/08/04/230000)
    BAYES_PARAMS = {'gamma': (0.01, 10),
                    'C': (0.1, 10)
                    }
    INT_PARAMS = []
    BAYES_NOT_OPT_PARAMS = {k: v[0] for k, v in NOT_OPT_PARAMS.items()}

    # 範囲選択検証曲線用パラメータ範囲
    VALIDATION_CURVE_PARAMS = {'gamma': (0.01, 10),
                    'C': (0.1, 10)
                    }

    def _train_param_generation(self, src_fit_params):
        """
        入力データから学習時パラメータの生成 (eval_set)
        
        Parameters
        ----------
        src_fit_params : Dict
            処理前の学習時パラメータ
        """
        return src_fit_params

    def _bayes_evaluate(self, gamma, C):
        """
         ベイズ最適化時の評価指標算出メソッド
        """
        # 最適化対象のパラメータ
        params = {'gamma': gamma,
                  'C': C
                  }
        params = self._int_conversion(params, self.int_params)  # 整数パラメータはint型に変換
        params.update(self.bayes_not_opt_params)  # 最適化対象以外のパラメータも追加
        # パイプライン処理のとき、パラメータに学習器名を追加
        params = self._add_learner_name(self.cv_model, params)
        # XGBoostのモデル作成
        cv_model = copy.deepcopy(self.cv_model)
        cv_model.set_params(**params)

        # cross_val_scoreでクロスバリデーション
        scores = cross_val_score(cv_model, self.X, self.y, cv=self.cv,
                                 scoring=self.scoring, fit_params=self.fit_params, n_jobs=-1)
        val = scores.mean()

        # スクラッチでクロスバリデーション
        # scores = []
        # for train, test in self.cv.split(self.X, self.y):
        #     X_train = self.X[train]
        #     y_train = self.y[train]
        #     X_test = self.X[test]
        #     y_test = self.y[test]
        #     cv_model.fit(X_train,
        #              y_train,
        #              eval_set=[(X_train, y_train)],
        #              early_stopping_rounds=self.early_stopping_rounds,
        #              verbose=0
        #              )
        #     pred = cv_model.predict(X_test)
        #     score = r2_score(y_test, pred)
        #     scores.append(score)
        # val = sum(scores)/len(scores)

        return val