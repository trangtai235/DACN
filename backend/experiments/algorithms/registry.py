from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.naive_bayes import ComplementNB
ALGORITHMS={
 'logistic_regression':{'name':'TF-IDF + Logistic Regression','parameter':'C','values':[0.5,2.0,8.0],'factory':lambda v:LogisticRegression(C=v,class_weight='balanced',max_iter=1000,solver='liblinear',random_state=42)},
 'linear_svm':{'name':'TF-IDF + Linear SVM','parameter':'C','values':[0.5,2.0,8.0],'factory':lambda v:LinearSVC(C=v,class_weight='balanced',random_state=42,max_iter=5000)},
 'complement_nb':{'name':'TF-IDF + Complement Naive Bayes','parameter':'alpha','values':[0.1,0.5,1.0],'factory':lambda v:ComplementNB(alpha=v)}
}
def algorithm(key):
    if key not in ALGORITHMS:raise ValueError('Thuật toán chưa đăng ký.')
    return ALGORITHMS[key]
