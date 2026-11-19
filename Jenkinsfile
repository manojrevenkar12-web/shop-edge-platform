// Shop release pipeline: tests, SonarQube quality gate, image, 10% canary analysed against Prometheus, promote.
// A release never cleans the Varnish cache; pages refresh through tag bans and grace.
pipeline {
  agent { kubernetes { yamlFile 'ops/jenkins/agent.yaml' } }
  options { timeout(time: 60, unit: 'MINUTES'); disableConcurrentBuilds() }
  environment {
    IMAGE = "europe-west3-docker.pkg.dev/shop-prod/shop/php:${env.GIT_COMMIT.take(12)}"
    PROMETHEUS = 'http://frontend.gmp-public.svc:9090'
  }
  stages {
    stage('Test') {
      steps { container('php') { sh 'composer install --no-interaction && vendor/bin/phpunit --log-junit reports/junit.xml' } }
      post { always { junit 'reports/junit.xml' } }
    }
    stage('SonarQube') {
      steps {
        container('sonar') { withSonarQubeEnv('sonarqube') { sh 'sonar-scanner' } }
        timeout(time: 10, unit: 'MINUTES') { waitForQualityGate abortPipeline: true }
      }
    }
    stage('Image') {
      steps { container('kaniko') { sh "/kaniko/executor --context . --destination ${IMAGE}" } }
    }
    stage('Canary 10%') {
      steps {
        container('tools') {
          sh "kubectl argo rollouts set image shop-php php=${IMAGE} -n shop"
          sh 'kubectl argo rollouts status shop-php -n shop --timeout 10m || true'
          script {
            def canary = sh(returnStdout: true, script: "kubectl get rs -n shop -l app=shop-php --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.labels.rollouts-pod-template-hash}'").trim()
            def stable = sh(returnStdout: true, script: "kubectl get rollout shop-php -n shop -o jsonpath='{.status.stableRS}'").trim()
            def rc = sh(returnStatus: true, script: "python -m sep.release.canary_check --prometheus ${PROMETHEUS} --canary-hash ${canary} --stable-hash ${stable}")
            if (rc != 0) {
              sh 'kubectl argo rollouts abort shop-php -n shop'
              error('Canary analysis failed: rolled back')
            }
          }
        }
      }
    }
    stage('Promote') {
      steps { container('tools') { sh 'kubectl argo rollouts promote shop-php -n shop && kubectl argo rollouts status shop-php -n shop --timeout 15m' } }
    }
  }
}
