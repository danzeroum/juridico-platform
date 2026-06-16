from locust import HttpUser, task, between


class GatewayUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def health(self):
        self.client.get('/health')
