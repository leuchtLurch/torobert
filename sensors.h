String motion;
String message;

void setup() {
  Serial.begin(9600);
  pinMode(4, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
    if (digitalRead(4) == 1) {
        motion="1";
        digitalWrite(LED_BUILTIN, LOW);
    } else {
        motion="0";
        digitalWrite(LED_BUILTIN, HIGH);
    }
    message = "{\"motion\": "+motion+"}";
    Serial.println(message);
    delay(50);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(50);
    digitalWrite(LED_BUILTIN, HIGH);
    delay(300);
}
