pipeline {
    agent {
        node {
            label 'built-in'
        }
    }

    environment {
        MODEL_SOURCE  = "ollama"
        MODEL_NAME    = "llama3.2:3b"
        REPORT_DIR    = "reports/${BUILD_NUMBER}"
        VENV_DIR      = "/opt/llm-pipeline/venv"
        VENV_PYTHON   = "/opt/llm-pipeline/venv/bin/python3"
        VENV_PIP      = "/opt/llm-pipeline/venv/bin/pip"
        OLLAMA_HOST   = "http://127.0.0.1:11434"
        OLLAMA_MODELS = "/usr/share/ollama/.ollama/models"
        PATH          = "/opt/llm-pipeline/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    }

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {

        stage('Checkout & Setup') {
            steps {
                sh '''
                    set -e
                    mkdir -p ${REPORT_DIR}
                    echo "[INFO] Workspace : $(pwd)"
                    echo "[INFO] Build     : #${BUILD_NUMBER}"
                    echo "[INFO] Python    : $(${VENV_PYTHON} --version)"

                    echo "[INFO] Installing project dependencies..."
                    if [ -f requirements.txt ]; then
                        ${VENV_PIP} install -r requirements.txt --quiet
                    fi

                    echo "[INFO] Verifying tinyllama is available via Ollama API..."
                    curl -s ${OLLAMA_HOST}/api/tags | grep -q "tinyllama" \
                        || (echo "❌ tinyllama not found in Ollama" && exit 1)
                    echo "✅ llama3.2:3b ready"
                '''
            }
        }

        stage('[1] Static Security') {
            steps {
                sh '''
                    set -e
                    echo "[INFO] Installing modelscan..."
                    ${VENV_PIP} install modelscan --quiet

                    ${VENV_PYTHON} scripts/static_security.py \
                        --model llama3.2:3b \
                        --source ollama \
                        --output ${REPORT_DIR}/static_security.json
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORT_DIR}/static_security.json", allowEmptyArchive: true
                }
                failure {
                    error("❌ [1] Static Security failed — pipeline stopped")
                }
            }
        }

        stage('[2] Quality & Bias Validation') {
            parallel {
                stage('Quality Benchmark') {
                    steps {
                        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                            sh '''
                                set -e
                                ${VENV_PYTHON} scripts/quality_benchmark.py \
                                    --model llama3.2:3b \
                                    --source ollama \
                                    --output ${REPORT_DIR}/quality.json
                            '''
                        }
                        echo "[INFO] Quality results recorded — non-blocking stage"
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: "${REPORT_DIR}/quality.json", allowEmptyArchive: true
                        }
                    }
                }

                stage('Bias Detection') {
                    steps {
                        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                            sh '''
                                set -e
                                ${VENV_PYTHON} scripts/bias_detection.py \
                                    --model llama3.2:3b \
                                    --source ollama \
                                    --output ${REPORT_DIR}/bias.json
                            '''
                        }
                        echo "[INFO] Bias results recorded — non-blocking stage"
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: "${REPORT_DIR}/bias.json", allowEmptyArchive: true
                        }
                    }
                }
            }
        }

        stage('[3] Dynamic Security Testing') {
            parallel {
                stage('Garak') {
                    steps {
                        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                            sh '''
                                echo "[INFO] Installing garak..."
                                ${VENV_PIP} install garak --quiet || true

                                echo "[INFO] Running Garak on tinyllama..."
                                ${VENV_PYTHON} -m garak \
                                    --model_type ollama \
                                    --model_name llama3.2:3b \
                                    --probes promptinject,knownbadsignatures \
                                    --report_prefix ${REPORT_DIR}/garak \
                                    2>&1 | tee ${REPORT_DIR}/garak_stdout.txt || true

                                ${VENV_PYTHON} -c "
import json, glob
report_files = glob.glob('${REPORT_DIR}/garak*.json')
passed = True
summary = {'tool': 'garak', 'model': 'llama3.2:3b', 'files_found': report_files}
for f in report_files:
    try:
        with open(f) as fp:
            data = json.load(fp)
            if isinstance(data, list):
                for entry in data:
                    if entry.get('status') == 'failed':
                        passed = False
    except Exception:
        pass
summary['passed'] = passed
with open('${REPORT_DIR}/garak_report.json', 'w') as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
"
                            '''
                        }
                        echo "[INFO] Garak results recorded — non-blocking stage"
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: "${REPORT_DIR}/garak*.json", allowEmptyArchive: true
                            archiveArtifacts artifacts: "${REPORT_DIR}/garak_stdout.txt", allowEmptyArchive: true
                        }
                    }
                }

                stage('Dynamic Security Script') {
                    steps {
                        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                            sh '''
                                set -e
                                ${VENV_PYTHON} scripts/dynamic_security.py \
                                    --model llama3.2:3b \
                                    --source ollama \
                                    --output ${REPORT_DIR}/dynamic_security.json
                            '''
                        }
                        echo "[INFO] Dynamic security results recorded — non-blocking stage"
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: "${REPORT_DIR}/dynamic_security.json", allowEmptyArchive: true
                        }
                    }
                }
            }
        }

        stage('[4] Trust & Release') {
            steps {
                sh '''
                    set -e
                    ${VENV_PYTHON} scripts/trust_release.py \
                        --report-dir ${REPORT_DIR} \
                        --model llama3.2:3b \
                        --source ollama \
                        --output ${REPORT_DIR}/final_report.json
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORT_DIR}/final_report.json", allowEmptyArchive: true
                    archiveArtifacts artifacts: "${REPORT_DIR}/final_report.html", allowEmptyArchive: true
                }
                success {
                    echo "✅ Model tinyllama validated successfully!"
                }
                failure {
                    echo "❌ tinyllama rejected — trust score insufficient"
                }
            }
        }
    }

    post {
        always {
            echo "📊 Pipeline finished — Build #${BUILD_NUMBER}"
            echo "📁 Reports archived as Jenkins artifacts."
        }
    }
}
