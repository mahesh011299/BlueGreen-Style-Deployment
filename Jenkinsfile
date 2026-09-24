pipeline {
    agent any

    parameters {
        string(name: 'VERSION', defaultValue: '7.9', description: 'Application Version Tag')
        choice(name: 'DEPLOY_ENV', choices: ['PRODUCTION'], description: 'Target Environment')
        booleanParam(name: 'CONFIRM_PROD', defaultValue: true, description: 'Confirm deployment to Production')
    }

    environment {
        PATH      = "C:\\Program Files\\Docker\\Docker\\resources\\bin;${env.PATH}"
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
                    // Check if orders-blue is currently active inside the nginx config
                    def status = bat(
                        script: "@docker exec orders-proxy cat /etc/nginx/conf.d/default.conf | findstr orders-blue >nul 2>&1",
                        returnStatus: true
                    )

                    if (status == 0) {
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
                    def sha = bat(script: "@git rev-parse --short HEAD", returnStdout: true).trim()
                    env.GIT_SHA = sha
                    bat "docker build --build-arg APP_VERSION=${params.VERSION} --build-arg GIT_COMMIT=${env.GIT_SHA} -t ${APP_IMAGE}:${params.VERSION} -t ${APP_IMAGE}:${env.GIT_SHA} ."
                }
            }
        }

        stage('Start Candidate') {
            steps {
                bat """
                    docker rm -f ${env.CANDIDATE_SLOT} 2>nul || (exit 0)
                    docker run -d --name ${env.CANDIDATE_SLOT} --network ${env.NETWORK} -p ${env.CANDIDATE_PORT}:5000 -e APP_VERSION=${params.VERSION} -e GIT_COMMIT=${env.GIT_SHA} -e DB_HOST=${env.DB_HOST} ${APP_IMAGE}:${params.VERSION}
                """
            }
        }

        stage('Health & Integration Validation') {
            steps {
                script {
                    echo "Validating candidate container health..."
                    timeout(time: 45, unit: 'SECONDS') {
                        waitUntil {
                            def health = bat(
                                script: "@docker inspect --format=\"{{.State.Health.Status}}\" ${env.CANDIDATE_SLOT}",
                                returnStdout: true
                            ).trim()
                            return health.contains("healthy")
                        }
                    }

                    echo "Testing Candidate HTTP and DB connectivity..."
                    bat """
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
                    bat """
                        docker exec orders-proxy sed -i "s/${env.ACTIVE_SLOT}/${env.CANDIDATE_SLOT}/g" /etc/nginx/conf.d/default.conf
                        docker exec orders-proxy nginx -s reload
                    """
                }
            }
        }

        stage('Old Version Cleanup') {
            steps {
                bat """
                    docker stop ${env.ACTIVE_SLOT} 2>nul || (exit 0)
                    docker rm ${env.ACTIVE_SLOT} 2>nul || (exit 0)
                """
            }
        }

        stage('Deployment Verification') {
            steps {
                bat "curl -s http://localhost:8080/ | findstr \"${params.VERSION}\""
            }
        }
    }

    post {
        failure {
            echo "Deployment FAILED! Initiating automatic candidate cleanup..."
            bat "docker rm -f %CANDIDATE_SLOT% 2>nul || (exit 0)"
        }
        success {
            echo "Production Blue-Green deployment completed successfully!"
        }
    }
}