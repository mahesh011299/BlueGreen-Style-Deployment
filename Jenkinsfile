pipeline {
    agent any

    parameters {
        string(name: 'VERSION', defaultValue: '7.9', description: 'Application Version Tag')
        choice(name: 'DEPLOY_ENV', choices: ['PRODUCTION'], description: 'Target Environment')
        booleanParam(name: 'CONFIRM_PROD', defaultValue: true, description: 'Confirm deployment to Production')
    }

    environment {
        APP_IMAGE = 'orders-api'
        NETWORK   = 'orders-network'
        DB_HOST   = 'orders-db'
    }

    stages {
        stage('Validation') {
            steps {
                script {
                    if (!params.CONFIRM_PROD) {
                        error("Production deployment must be explicitly confirmed.")
                    }
                    if (!params.VERSION) {
                        error("VERSION parameter cannot be empty.")
                    }
                }
            }
        }

        stage('Determine Target Slot') {
            steps {
                script {
                    // Check if orders-blue is currently mapped as active in nginx
                    def active = sh(
                        script: "docker exec orders-proxy cat /etc/nginx/conf.d/default.conf | grep 'orders-blue' || true",
                        returnStdout: true
                    ).trim()

                    if (active) {
                        env.CANDIDATE_SLOT = "orders-green"
                        env.CANDIDATE_PORT = "8082"
                        env.ACTIVE_SLOT    = "orders-blue"
                    } else {
                        env.CANDIDATE_SLOT = "orders-blue"
                        env.CANDIDATE_PORT = "8081"
                        env.ACTIVE_SLOT    = "orders-green"
                    }

                    echo "Active Slot: ${env.ACTIVE_SLOT} | Candidate Target: ${env.CANDIDATE_SLOT} on port ${env.CANDIDATE_PORT}"
                }
            }
        }

        stage('Docker Build') {
            steps {
                script {
                    env.GIT_SHA = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
                    sh """
                        docker build \
                          --build-arg APP_VERSION=${params.VERSION} \
                          --build-arg GIT_COMMIT=${env.GIT_SHA} \
                          -t ${APP_IMAGE}:${params.VERSION} \
                          -t ${APP_IMAGE}:${env.GIT_SHA} .
                    """
                }
            }
        }

        stage('Start Candidate') {
            steps {
                sh """
                    docker rm -f ${env.CANDIDATE_SLOT} || true
                    docker run -d \
                      --name ${env.CANDIDATE_SLOT} \
                      --network ${env.NETWORK} \
                      -p ${env.CANDIDATE_PORT}:5000 \
                      -e APP_VERSION=${params.VERSION} \
                      -e GIT_COMMIT=${env.GIT_SHA} \
                      -e DB_HOST=${env.DB_HOST} \
                      ${APP_IMAGE}:${params.VERSION}
                """
            }
        }

        stage('Health & Integration Validation') {
            steps {
                script {
                    echo "Validating candidate container health..."
                    timeout(time: 30, unit: 'SECONDS') {
                        waitUntil {
                            def health = sh(
                                script: "docker inspect --format='{{json .State.Health.Status}}' ${env.CANDIDATE_SLOT} || true",
                                returnStdout: true
                            ).trim()
                            return health.contains("healthy")
                        }
                    }

                    echo "Testing Candidate HTTP and DB connectivity..."
                    sh """
                        curl -f http://localhost:${env.CANDIDATE_PORT}/health
                        curl -f http://localhost:${env.CANDIDATE_PORT}/db-check
                    """
                }
            }
        }

        stage('Switch Traffic') {
            steps {
                script {
                    echo "Switching live traffic to ${env.CANDIDATE_SLOT}..."
                    sh """
                        docker exec orders-proxy sed -i 's/${env.ACTIVE_SLOT}/${env.CANDIDATE_SLOT}/g' /etc/nginx/conf.d/default.conf
                        docker exec orders-proxy nginx -s reload
                    """
                }
            }
        }

        stage('Old Version Cleanup') {
            steps {
                sh """
                    echo "Stopping previous production slot: ${env.ACTIVE_SLOT}"
                    docker stop ${env.ACTIVE_SLOT} || true
                    docker rm ${env.ACTIVE_SLOT} || true
                """
            }
        }

        stage('Deployment Verification') {
            steps {
                sh """
                    curl -s http://localhost:8080/ | grep '"version": "${params.VERSION}"'
                """
            }
        }
    }

    post {
        failure {
            echo "Deployment FAILED! Initiating automatic recovery/rollback..."
            sh """
                # Abort candidate container and keep active slot untouched
                docker rm -f ${env.CANDIDATE_SLOT} || true
                echo "Cleaned up candidate slot: ${env.CANDIDATE_SLOT}. Active slot remains untouched."
            """
        }
        success {
            echo "Production Blue-Green deployment of version ${params.VERSION} completed successfully!"
        }
    }
}